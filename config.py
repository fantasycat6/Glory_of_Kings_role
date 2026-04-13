"""
配置文件 - 王者荣耀英雄统计网站
"""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'wzry-secret-key-2026'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 服务器配置
    PORT = int(os.environ.get('PORT', 5000))
    
    # 数据库配置（SQLite）
    SQLITE_PATH = os.environ.get('SQLITE_PATH', os.path.join(BASE_DIR, 'data', 'wzry.db'))
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{SQLITE_PATH}'
    
    # 调试模式配置
    @staticmethod
    def get_debug_mode():
        flask_env = os.environ.get('FLASK_ENV', '').lower()
        flask_debug = os.environ.get('FLASK_DEBUG', '').lower()
        
        if flask_env == 'production':
            return False
        elif flask_env == 'development':
            return True
        elif flask_debug in ['true', '1', 'yes']:
            return True
        else:
            return True


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
