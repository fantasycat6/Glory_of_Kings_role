"""
Flask 应用工厂和入口点
王者荣耀英雄统计网站
"""
from flask import Flask, render_template, request, jsonify
from flask_login import LoginManager
from models import db, User, init_default_data
from config import config
import os


def create_app(config_name=None):
    """应用工厂"""
    app = Flask(__name__)
    
    # 加载配置
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    app.config.from_object(config[config_name])
    
    # 初始化扩展
    db.init_app(app)
    
    # Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '请先登录再访问此页面'
    login_manager.login_message_category = 'warning'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # 注册蓝图
    from auth import auth_bp
    from routes import main_bp
    from admin import admin_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    
    # 错误处理
    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not found'}), 404
        return render_template('error.html', message='页面未找到'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('error.html', message='服务器内部错误'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Forbidden'}), 403
        return render_template('error.html', message='无权访问此页面'), 403
    
    # 创建表并初始化数据
    with app.app_context():
        db.create_all()
        init_default_data()
        # 扫描并同步备份文件
        scan_backup_files(app)
    
    return app


def scan_backup_files(app):
    """扫描 backup 文件夹，将备份文件同步到数据库"""
    from models import BackupFile
    from datetime import datetime
    import os
    
    backup_dir = os.path.join(os.path.dirname(__file__), 'backup')
    if not os.path.exists(backup_dir):
        return
    
    # 获取数据库中已有的备份文件名
    existing_files = {b.filename for b in BackupFile.query.all()}
    
    # 扫描 backup 文件夹
    for filename in os.listdir(backup_dir):
        if filename in existing_files:
            continue
            
        filepath = os.path.join(backup_dir, filename)
        if not os.path.isfile(filepath):
            continue
        
        # 判断文件类型
        if filename.endswith('.db'):
            file_type = 'database'
            backup_type = 'manual' if not filename.startswith('auto_') else 'auto'
            description = '数据库备份'
        elif filename.endswith('.json'):
            file_type = 'json'
            backup_type = 'manual' if not filename.startswith('auto_') else 'auto'
            description = '英雄数据备份'
        else:
            continue
        
        # 使用相对路径存储
        relative_path = os.path.join('backup', filename)
        
        # 添加到数据库
        try:
            backup_record = BackupFile(
                filename=filename,
                filepath=relative_path,
                file_size=os.path.getsize(filepath),
                backup_type=backup_type,
                file_type=file_type,
                description=description,
                created_at=datetime.fromtimestamp(os.path.getmtime(filepath))
            )
            db.session.add(backup_record)
        except Exception as e:
            print(f"扫描备份文件失败 {filename}: {e}")
    
    try:
        db.session.commit()
        print(f"备份文件扫描完成，共发现 {len([f for f in os.listdir(backup_dir) if f.endswith(('.db', '.json'))])} 个备份文件")
    except Exception as e:
        db.session.rollback()
        print(f"备份文件扫描失败: {e}")


if __name__ == '__main__':
    app = create_app()
    # 从 app.config 读取配置，确保 .env 文件被加载
    port = app.config.get('PORT', 5000)
    debug = app.config.get('FLASK_DEBUG', True)
    
    print(f"\n{'='*50}")
    print(f"  王者荣耀英雄统计网站")
    print(f"  访问地址: http://127.0.0.1:{port}")
    print(f"  默认管理员: admin / admin123")
    print(f"{'='*50}\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
