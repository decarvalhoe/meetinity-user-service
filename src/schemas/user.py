from marshmallow import (
    Schema,
    fields,
    validates,
    ValidationError,
    pre_load,
    post_dump,
)
from src.models import User


class UserBaseSchema(Schema):
    email = fields.Email(required=True)
    name = fields.Str(required=True, validate=lambda s: 1 <= len(s) <= 120)
    title = fields.Str(validate=lambda s: len(s) <= 120)
    company = fields.Str(validate=lambda s: len(s) <= 120)
    bio = fields.Str(validate=lambda s: len(s) <= 2000)
    skills = fields.List(fields.Str(), load_default=list, dump_default=list)
    interests = fields.List(fields.Str(), load_default=list, dump_default=list)
    location = fields.Str(validate=lambda s: len(s) <= 120)
    experience_years = fields.Int(load_default=0)
    industry = fields.Str(validate=lambda s: len(s) <= 120)
    linkedin_url = fields.URL(allow_none=True, load_default=None)
    is_active = fields.Bool(load_default=True)

    @pre_load
    def preprocess(self, data, **kwargs):
        if 'email' in data and isinstance(data['email'], str):
            data['email'] = data['email'].lower()
        return data

    @validates('experience_years')
    def validate_exp(self, value):
        if value is not None and value < 0:
            raise ValidationError('experience_years must be >= 0')

    @post_dump
    def split_fields(self, data, **kwargs):
        for key in ['skills', 'interests']:
            val = data.get(key)
            if isinstance(val, str):
                data[key] = [s for s in val.split(',') if s]
        return data


class UserSchema(UserBaseSchema):
    id = fields.Int(dump_only=True)
    photo_url = fields.Str(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    last_login = fields.DateTime(allow_none=True, dump_only=True)


class UserUpdateSchema(UserBaseSchema):
    email = fields.Email(required=False)
    name = fields.Str(required=False, validate=lambda s: 1 <= len(s) <= 120)


def user_to_dict(user: User):
    schema = UserSchema()
    data = schema.dump(user)
    for key in ['skills', 'interests']:
        data[key] = getattr(user, key + '_list')()
    return data


def load_user(data, instance=None):
    schema = UserBaseSchema()
    result = schema.load(data)
    if instance is None:
        instance = User()
    for key, value in result.items():
        if key in ['skills', 'interests']:
            setattr(instance, key, ','.join(value))
        else:
            setattr(instance, key, value)
    return instance
