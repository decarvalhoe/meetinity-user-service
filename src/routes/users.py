from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
from marshmallow import ValidationError

from src.models import db, User
from src.schemas.user import user_to_dict, load_user, UserUpdateSchema
from src.validators.query import parse_list_args
from src.services.uploads import save_photo

bp = Blueprint('users', __name__, url_prefix='/users')


def error_response(code, message, details=None):
    payload = {'error': {'code': code, 'message': message}}
    if details is not None:
        payload['error']['details'] = details
    return jsonify(payload), code


@bp.route('', methods=['POST'])
def create_user():
    data = request.get_json() or {}
    try:
        user = load_user(data)
        db.session.add(user)
        db.session.commit()
    except ValidationError as err:
        return error_response(422, 'validation error', err.messages)
    except IntegrityError:
        db.session.rollback()
        return error_response(400, 'email already exists')
    return jsonify({'user': user_to_dict(user)}), 201


@bp.route('', methods=['GET'])
def list_users():
    args = parse_list_args(request.args)
    query = User.query
    if args['industry']:
        query = query.filter(User.industry == args['industry'])
    if args['location']:
        query = query.filter(User.location == args['location'])
    if args['min_experience'] is not None:
        query = query.filter(User.experience_years >= args['min_experience'])
    if args['max_experience'] is not None:
        query = query.filter(User.experience_years <= args['max_experience'])
    for skill in args['skills']:
        query = query.filter(User.skills.ilike(f'%{skill}%'))
    total = query.count()
    sort_attr = getattr(User, args['sort_field'])
    if args['sort_order'] == 'desc':
        sort_attr = sort_attr.desc()
    query = query.order_by(sort_attr)
    items = (
        query.offset((args['page'] - 1) * args['per_page'])
        .limit(args['per_page'])
        .all()
    )
    return jsonify({
        'items': [user_to_dict(u) for u in items],
        'page': args['page'],
        'per_page': args['per_page'],
        'total': total,
    })


@bp.route('/search', methods=['GET'])
def search_users():
    args = parse_list_args(request.args)
    q = request.args.get('q', '')
    if not q:
        return jsonify(
            {
                'items': [],
                'page': args['page'],
                'per_page': args['per_page'],
                'total': 0,
            }
        )
    like = f'%{q}%'
    query = User.query.filter(
        (User.name.ilike(like)) |
        (User.title.ilike(like)) |
        (User.company.ilike(like)) |
        (User.bio.ilike(like)) |
        (User.skills.ilike(like)) |
        (User.interests.ilike(like))
    )
    total = query.count()
    sort_attr = getattr(User, args['sort_field'])
    if args['sort_order'] == 'desc':
        sort_attr = sort_attr.desc()
    items = (
        query.order_by(sort_attr)
        .offset((args['page'] - 1) * args['per_page'])
        .limit(args['per_page'])
        .all()
    )
    return jsonify(
        {
            'items': [user_to_dict(u) for u in items],
            'page': args['page'],
            'per_page': args['per_page'],
            'total': total,
        }
    )


@bp.route('/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return error_response(404, 'user not found')
    return jsonify({'user': user_to_dict(user)})


@bp.route('/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return error_response(404, 'user not found')
    data = request.get_json() or {}
    schema = UserUpdateSchema()
    try:
        loaded = schema.load(data)
    except ValidationError as err:
        return error_response(422, 'validation error', err.messages)
    for key, value in loaded.items():
        if key in ['skills', 'interests']:
            setattr(user, key, ','.join(value))
        else:
            setattr(user, key, value)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error_response(400, 'email already exists')
    return jsonify({'user': user_to_dict(user)})


@bp.route('/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return error_response(404, 'user not found')
    db.session.delete(user)
    db.session.commit()
    return '', 204


@bp.route('/<int:user_id>/photo', methods=['POST'])
def upload_photo(user_id):
    user = User.query.get(user_id)
    if not user:
        return error_response(404, 'user not found')
    if 'photo' not in request.files:
        return error_response(400, 'photo is required')
    file = request.files['photo']
    try:
        url = save_photo(file, user_id)
    except ValueError as e:
        return error_response(415, str(e))
    user.photo_url = url
    db.session.commit()
    return jsonify({'photo_url': url, 'user_id': user_id}), 201
