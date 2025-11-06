from .views import get_user_groups


def user_groups_context(request):
    """Контекстный процессор для добавления групп пользователя в каждый шаблон"""
    if request.user.is_authenticated and request.user.role in ['admin', 'teacher']:
        return {
            'user_groups': get_user_groups(request.user),
        }
    return {
        'user_groups': [],
    }




