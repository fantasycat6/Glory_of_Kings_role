"""
数据库模型 - 王者荣耀英雄统计网站
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json
import os

db = SQLAlchemy()

# 英雄数据文件路径
HEROES_JSON_PATH = os.path.join(os.path.dirname(__file__), 'data', 'heroes_official.json')
HERO_IMAGES_JSON_PATH = os.path.join(os.path.dirname(__file__), 'data', 'hero_images.json')


def load_heroes_from_json():
    """从JSON文件加载英雄数据"""
    try:
        with open(HEROES_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('heroes', []), data.get('defaultHeroNames', [])
    except Exception as e:
        print(f"加载英雄数据失败: {e}")
        return [], []


def load_hero_images_from_json():
    """从JSON文件加载英雄图片数据"""
    try:
        with open(HERO_IMAGES_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载英雄图片数据失败: {e}")
        return {}


class User(UserMixin, db.Model):
    """用户表"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # 关系
    accounts = db.relationship('Account', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<User {self.username}>'


class Account(db.Model):
    """游戏账号表"""
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    login_type = db.Column(db.String(20), default='qq')  # qq / wechat
    platform = db.Column(db.String(20), default='android')  # android / ios
    sort_order = db.Column(db.Integer, default=0)  # 排序顺序
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # 关系
    regions = db.relationship('Region', backref='account', lazy=True, cascade='all, delete-orphan', order_by='Region.sort_order')
    hero_ownerships = db.relationship('HeroOwnership', backref='account', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'login_type': self.login_type,
            'platform': self.platform,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<Account {self.name}>'


class Region(db.Model):
    """区服表"""
    __tablename__ = 'regions'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, default=0)  # 排序顺序
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # 关系
    hero_ownerships = db.relationship('HeroOwnership', backref='region', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<Region {self.name}>'


class Hero(db.Model):
    """英雄表"""
    __tablename__ = 'heroes'
    
    name = db.Column(db.String(50), primary_key=True)
    role = db.Column(db.String(50), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    
    # 关系
    ownerships = db.relationship('HeroOwnership', backref='hero', lazy=True, cascade='all, delete-orphan')
    
    @classmethod
    def get_all_roles(cls):
        """获取所有职业分类"""
        heroes = cls.query.all()
        role_set = set()
        for hero in heroes:
            for role in hero.role.split('/'):
                role_set.add(role.strip())
        return sorted(list(role_set))
    
    @classmethod
    def get_default_heroes(cls):
        """获取默认英雄"""
        return cls.query.filter_by(is_default=True).order_by(cls.name).all()
    
    @classmethod
    def get_sorted_by_name(cls):
        """按名称排序获取所有英雄"""
        return cls.query.order_by(cls.name).all()
    
    @classmethod
    def search(cls, query):
        """搜索英雄"""
        search_pattern = f'%{query}%'
        return cls.query.filter(
            db.or_(
                cls.name.like(search_pattern),
                cls.role.like(search_pattern)
            )
        ).order_by(cls.name).all()
    
    def to_dict(self):
        return {
            'name': self.name,
            'role': self.role,
            'is_default': self.is_default
        }
    
    def __repr__(self):
        return f'<Hero {self.name}>'


class HeroOwnership(db.Model):
    """英雄拥有记录表"""
    __tablename__ = 'hero_ownership'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    region_id = db.Column(db.Integer, db.ForeignKey('regions.id'), nullable=False)
    hero_name = db.Column(db.String(50), db.ForeignKey('heroes.name'), nullable=False)
    obtained_at = db.Column(db.DateTime, default=datetime.now)
    
    # 联合唯一约束
    __table_args__ = (
        db.UniqueConstraint('account_id', 'region_id', 'hero_name', name='unique_hero_ownership'),
    )
    
    @classmethod
    def get_owned_heroes(cls, account_id, region_id):
        """获取指定区服已拥有的英雄名称列表"""
        records = cls.query.filter_by(account_id=account_id, region_id=region_id).all()
        return [record.hero_name for record in records]
    
    @classmethod
    def get_stats(cls, account_id, region_id):
        """获取统计信息"""
        owned_heroes = cls.get_owned_heroes(account_id, region_id)
        all_heroes = Hero.query.all()
        total = len(all_heroes)
        owned = len(owned_heroes)
        
        # 按职业统计
        by_role = {}
        for hero in all_heroes:
            roles = hero.role.split('/')
            for role in roles:
                role = role.strip()
                if role not in by_role:
                    by_role[role] = {'total': 0, 'owned': 0}
                by_role[role]['total'] += 1
                if hero.name in owned_heroes:
                    by_role[role]['owned'] += 1
        
        return {
            'total': total,
            'owned': owned,
            'percentage': round((owned / total * 100)) if total > 0 else 0,
            'byRole': by_role
        }
    
    @classmethod
    def batch_update(cls, account_id, region_id, hero_names, owned):
        """批量更新英雄拥有状态"""
        if owned:
            # 添加拥有的英雄
            for hero_name in hero_names:
                existing = cls.query.filter_by(
                    account_id=account_id, 
                    region_id=region_id, 
                    hero_name=hero_name
                ).first()
                if not existing:
                    ownership = cls(
                        account_id=account_id,
                        region_id=region_id,
                        hero_name=hero_name
                    )
                    db.session.add(ownership)
        else:
            # 移除拥有的英雄
            cls.query.filter(
                cls.account_id == account_id,
                cls.region_id == region_id,
                cls.hero_name.in_(hero_names)
            ).delete(synchronize_session=False)
        
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'region_id': self.region_id,
            'hero_name': self.hero_name,
            'obtained_at': self.obtained_at.isoformat() if self.obtained_at else None
        }


class BackupFile(db.Model):
    """备份文件表"""
    __tablename__ = 'backup_files'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)
    backup_type = db.Column(db.String(20), default='manual')  # manual / auto
    description = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    def format_size(self):
        """格式化文件大小"""
        if not self.file_size:
            return "未知"
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0 or unit == 'GB':
                return f"{size:.1f} {unit}"
            size /= 1024.0
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'filepath': self.filepath,
            'file_size': self.file_size,
            'file_size_formatted': self.format_size(),
            'backup_type': self.backup_type,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_at_formatted': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '-'
        }


def init_default_data():
    """初始化默认数据"""
    # 加载英雄数据
    heroes, default_hero_names = load_heroes_from_json()
    
    # 检查是否已有英雄数据
    if Hero.query.count() == 0 and heroes:
        print(f"初始化 {len(heroes)} 位英雄数据...")
        for hero_data in heroes:
            hero = Hero(
                name=hero_data['name'],
                role=hero_data['role'],
                is_default=hero_data['name'] in default_hero_names
            )
            db.session.add(hero)
        print("英雄数据初始化完成")
    
    # 创建默认管理员账号
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        print("创建默认管理员账号...")
        admin = User(
            username='admin',
            email='admin@example.com',
            is_admin=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        print("默认管理员账号已创建: admin / admin123")
    
    db.session.commit()


def get_hero_images():
    """获取英雄图片数据"""
    return load_hero_images_from_json()
