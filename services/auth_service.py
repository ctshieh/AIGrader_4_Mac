from database.db_manager import login_user, get_user_id_by_session, get_user_by_id, create_session, delete_session
import uuid

def validate_session(token):
    user_id = get_user_id_by_session(token)
    if user_id:
        return get_user_by_id(user_id)
    return None

def logout_user(token):
    delete_session(token)
