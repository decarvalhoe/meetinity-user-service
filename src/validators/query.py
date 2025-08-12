ALLOWED_SORT_FIELDS = {
    'created_at', 'updated_at', 'last_login', 'experience_years', 'name'
}


def parse_list_args(args):
    def get_int(name, default):
        try:
            return int(args.get(name, default))
        except (TypeError, ValueError):
            return default

    page = max(get_int('page', 1), 1)
    per_page = get_int('per_page', 20)
    if per_page <= 0:
        per_page = 20
    per_page = min(per_page, 100)

    sort = args.get('sort', 'created_at:asc')
    if ':' in sort:
        field, order = sort.split(':', 1)
    else:
        field, order = sort, 'asc'
    if field not in ALLOWED_SORT_FIELDS:
        field = 'created_at'
    order = 'desc' if order == 'desc' else 'asc'

    skills_raw = args.get('skills', '')
    skills = [s.strip() for s in skills_raw.split(',') if s.strip()]

    def parse_optional_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return {
        'page': page,
        'per_page': per_page,
        'sort_field': field,
        'sort_order': order,
        'industry': args.get('industry'),
        'location': args.get('location'),
        'min_experience': parse_optional_int(args.get('min_experience')),
        'max_experience': parse_optional_int(args.get('max_experience')),
        'skills': skills,
    }
