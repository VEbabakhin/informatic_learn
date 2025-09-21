from .views import get_user_groups, get_selected_group


def user_groups_context(request):
    """Контекстный процессор для добавления групп пользователя в каждый шаблон"""
    if request.user.is_authenticated and request.user.role in ['admin', 'teacher']:
        return {
            'user_groups': get_user_groups(request.user),
            'selected_group': get_selected_group(request.user, request.session),
            'selected_group_id': request.session.get('selected_group_id')
        }
    return {
        'user_groups': [],
        'selected_group': None,
        'selected_group_id': None
    }

