from flask import Flask
from pathlib import Path

def create_app(config_path=None):
    """Flask application factory."""
    # Resolve static/template folders to src/music_player/ with absolute paths
    base_dir = Path(__file__).resolve().parent.parent
    template_folder = str(base_dir / 'web' / 'templates')
    static_folder = str(base_dir / 'static')

    app = Flask(__name__,
                template_folder=template_folder,
                static_folder=static_folder,
                static_url_path='/static')
    
    # Configuration
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload
    app.config['UPLOAD_TEMP'] = Path('/tmp/music-upload')
    app.config['MEDIA_BASE'] = Path('/opt/music-player/media')
    app.config['CATALOG_PATH'] = Path('/opt/music-player/catalog.json')
    app.config['UPDATE_DIR'] = Path('/opt/music-player/updates')
    app.config['UPDATE_ROOT'] = Path('/opt/music-player')
    app.config['UPDATE_SETTINGS_PATH'] = Path('/opt/music-player/update_settings.json')
    
    # Create required directories
    app.config['UPLOAD_TEMP'].mkdir(exist_ok=True)
    for subdir in ['audio', 'images', 'video', 'thumbnails']:
        (app.config['MEDIA_BASE'] / subdir).mkdir(parents=True, exist_ok=True)
    
    # Initialize update handler and start worker thread
    from music_player.web.update_handler import UpdateHandler
    update_handler = UpdateHandler(app.config['UPDATE_ROOT'])
    update_handler.start_worker()
    
    # Store reference for shutdown
    app.update_handler = update_handler
    
    # Register blueprints
    from music_player.web.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Cleanup on shutdown
    @app.teardown_appcontext
    def shutdown_update_worker(exception=None):
        if hasattr(app, 'update_handler'):
            app.update_handler.stop_worker()
    
    # Error handlers
    @app.errorhandler(400)
    def bad_request(error):
        return {'error': str(error.description)}, 400
    
    @app.errorhandler(500)
    def internal_error(error):
        return {'error': 'Internal server error'}, 500
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
