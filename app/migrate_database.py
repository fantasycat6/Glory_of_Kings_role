"""
数据库迁移脚本
为Hero表添加新字段
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .models import db, Hero, load_heroes_from_json
from .config import config
from datetime import datetime
from flask import Flask


def migrate_database(app=None):
    """执行数据库迁移"""
    if app is None:
        app = Flask(__name__)
        config_name = os.environ.get('FLASK_ENV', 'default')
        app.config.from_object(config[config_name])
        db.init_app(app)
    
    with app.app_context():
        try:
            print("开始数据库迁移...")
            
            from sqlalchemy import text
            
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('heroes')]
            
            has_pinyin = 'pinyin' in columns
            has_pub_time = 'pub_time' in columns
            has_image = 'image' in columns
            has_url = 'url' in columns
            
            if has_pinyin and has_pub_time and has_image and has_url:
                print("数据库已包含所有字段，无需添加新列。")
            else:
                if not has_pinyin:
                    try:
                        db.session.execute(text('ALTER TABLE heroes ADD COLUMN pinyin VARCHAR(100)'))
                        print("添加字段: pinyin")
                    except Exception as e:
                        print(f"添加 pinyin 字段跳过（可能已存在）: {e}")
                
                if not has_pub_time:
                    try:
                        db.session.execute(text('ALTER TABLE heroes ADD COLUMN pub_time DATE'))
                        print("添加字段: pub_time")
                    except Exception as e:
                        print(f"添加 pub_time 字段跳过（可能已存在）: {e}")
                
                if not has_image:
                    try:
                        db.session.execute(text('ALTER TABLE heroes ADD COLUMN image VARCHAR(500)'))
                        print("添加字段: image")
                    except Exception as e:
                        print(f"添加 image 字段跳过（可能已存在）: {e}")
                
                if not has_url:
                    try:
                        db.session.execute(text('ALTER TABLE heroes ADD COLUMN url VARCHAR(500)'))
                        print("添加字段: url")
                    except Exception as e:
                        print(f"添加 url 字段跳过（可能已存在）: {e}")
                
                db.session.commit()
                print("数据库迁移成功！")
            
            try:
                heroes_data, _ = load_heroes_from_json()
                
                for hero_data in heroes_data:
                    hero = Hero.query.get(hero_data['name'])
                    if hero:
                        if 'pinyin' in hero_data and not hero.pinyin:
                            hero.pinyin = hero_data['pinyin']
                        if 'pubTime' in hero_data and not hero.pub_time:
                            try:
                                hero.pub_time = datetime.strptime(hero_data['pubTime'], '%Y-%m-%d').date()
                            except ValueError:
                                pass
                        if 'image' in hero_data and not hero.image:
                            hero.image = hero_data['image']
                        if 'url' in hero_data and not hero.url:
                            hero.url = hero_data['url']
                
                db.session.commit()
                print("从heroes.json导入新字段数据成功！")
            except Exception as e:
                print(f"导入heroes.json数据时出错: {e}")
                db.session.rollback()
            
        except Exception as e:
            print(f"迁移失败: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()


if __name__ == '__main__':
    migrate_database()
