from flask import Blueprint, Response, render_template

errors = Blueprint("errors", __name__)

# Handle general server errors (500 and other Exceptions)
@errors.app_errorhandler(Exception)
def server_error(error):
    return Response(f"{error} (error)", status=500)

# Custom 404 error handler
@errors.app_errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

# Custom 401 error handler
@errors.app_errorhandler(401)
def unauthorized(error):
    return render_template('401.html'), 401