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
HEROES_JSON_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'heroes.json')


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
    """从JSON文件加载英雄图片数据（从heroes.json中提取）"""
    try:
        with open(HEROES_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        hero_images = {}
        for hero in data.get('heroes', []):
            name = hero.get('name', '')
            if name:
                hero_images[name] = {
                    'image': hero.get('image', ''),
                    'url': hero.get('url', '')
                }
        return hero_images
    except Exception as e:
        print(f"加载英雄图片数据失败: {e}")
        return {}


def parse_skin_image_id(image_url):
    """从皮肤图片URL中解析图片ID"""
    if not image_url:
        return ''
    
    # 定义基础URL模式
    base_patterns = [
        'https://game-1255653016.file.myqcloud.com/manage/compress/custom_wzry_E1/',
        'https://game-1255653016.file.myqcloud.com/manage/custom_wzry_E1/'
    ]
    
    for pattern in base_patterns:
        if pattern in image_url:
            # 提取文件名部分（不含查询参数）
            after_pattern = image_url.split(pattern)[1]
            if '?' in after_pattern:
                file_part = after_pattern.split('?')[0]
                # 去除扩展名
                if '.' in file_part:
                    return file_part.rsplit('.', 1)[0]
                return file_part
    
    # 检查是否是game.gtimg.cn格式
    if 'game.gtimg.cn' in image_url:
        try:
            parts = image_url.split('/')
            num1 = parts[-2]  # '141'
            num2_part = parts[-1].split('-')[-1].split('.')[0]  # '2'
            return f"{num1}-{num2_part}"
        except Exception:
            pass
    
    # 自定义URL，返回空
    return ''


def generate_skin_image_url(image_id, custom_image=''):
    """
    根据image_id生成皮肤图片URL
    
    优先级规则（明确用户手动输入的URL优先）：
    1. 优先级1：自定义皮肤头像URL（以http://或https://开头）- 用户明确输入的完整URL
    2. 优先级2：本地相对路径（/static/img/...）- 上传的本地图片
    3. 优先级3：图片ID - 需要用户手动复制到自定义URL字段
    
    Args:
        image_id: 皮肤图片ID，仅辅助生成预览用，不自动覆盖自定义URL
                  1. 腾讯官方格式: "141-2"
                  2. 压缩图片ID: "7dd876601a0d808b4d4071f31add095e"
                  3. PNG图片ID: "7dd876601a0d808b4d4071f31add095e"
        custom_image: 用户明确输入的完整URL（http/https或本地相对路径，优先级最高
    
    Returns:
        完整的皮肤图片URL
    """
    from .config import Config
    
    # 优先级1：自定义URL（http/https）或本地相对路径 - 用户明确输入的
    if custom_image:
        return custom_image
    
    # 优先级2：图片ID - 仅当没有自定义URL时才考虑使用
    if image_id:
        # 格式1：腾讯官方格式（包含"-"）
        if '-' in image_id:
            try:
                num1, num2 = image_id.split('-', 1)
                return Config.SKIN_IMAGE_BASE_URLS[2].format(num1=num1, num2=num2)
            except Exception:
                pass
        
        # 格式2和3：哈希格式（32位或类似的字符串）
        # 尝试使用压缩图片URL（第一个模板）
        try:
            return Config.SKIN_IMAGE_BASE_URLS[0].format(image_id=image_id)
        except Exception:
            # 尝试使用PNG图片URL（第二个模板）
            try:
                return Config.SKIN_IMAGE_BASE_URLS[1].format(image_id=image_id)
            except Exception:
                pass
    
    return ''


def load_hero_skins_from_json():
    """从JSON文件加载皮肤数据（从heroes.json中提取）"""
    try:
        with open(HEROES_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        skins = []
        for hero in data.get('heroes', []):
            hero_name = hero.get('name', '')
            hero_skins = hero.get('skins', [])
            for skin in hero_skins:
                # 处理对象数组格式（包含name和image字段）
                if isinstance(skin, dict):
                    skin_name = skin.get('name', '')
                    skin_image = skin.get('image', '')
                    skin_image_id = skin.get('image_id', '')
                    # 如果image_id为空但有image，尝试解析
                    if not skin_image_id and skin_image:
                        skin_image_id = parse_skin_image_id(skin_image)
                else:
                    # 处理字符串数组格式（兼容旧格式）
                    skin_name = skin
                    skin_image = ''
                    skin_image_id = ''
                
                if skin_name:  # 只添加非空的皮肤名称
                    skins.append({
                        'hero_name': hero_name,
                        'name': skin_name,
                        'image_id': skin_image_id,
                        'image': skin_image
                    })
        return skins
    except Exception as e:
        print(f"加载皮肤数据失败: {e}")
        return []


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
    
    def get_login_type_display(self):
        """获取登录类型的显示名称"""
        display_names = {
            'qq': 'QQ登录',
            'wechat': '微信登录'
        }
        return display_names.get(self.login_type, self.login_type)
    
    def get_platform_display(self):
        """获取设备平台的显示名称"""
        display_names = {
            'android': '安卓',
            'ios': '苹果'
        }
        return display_names.get(self.platform, self.platform)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'login_type': self.login_type,
            'login_type_display': self.get_login_type_display(),
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
    pinyin = db.Column(db.String(100), nullable=True)
    role = db.Column(db.String(50), nullable=False)
    pub_time = db.Column(db.Date, nullable=True)
    image = db.Column(db.String(500), nullable=True)
    url = db.Column(db.String(500), nullable=True)
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
                cls.pinyin.like(search_pattern),
                cls.role.like(search_pattern)
            )
        ).order_by(cls.name).all()
    
    def to_dict(self):
        return {
            'name': self.name,
            'pinyin': self.pinyin,
            'role': self.role,
            'pubTime': self.pub_time.strftime('%Y-%m-%d') if self.pub_time else None,
            'image': self.image,
            'url': self.url,
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


class Skin(db.Model):
    """皮肤表"""
    __tablename__ = 'skins'

    id = db.Column(db.Integer, primary_key=True)
    hero_name = db.Column(db.String(50), db.ForeignKey('heroes.name'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    image_id = db.Column(db.String(100), default='')
    image = db.Column(db.String(500), default='')

    # 关系
    hero = db.relationship('Hero', backref='skins', lazy=True)
    ownerships = db.relationship('SkinOwnership', backref='skin', lazy=True, cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('hero_name', 'name', name='unique_skin_name'),
    )

    @classmethod
    def get_skins_by_hero(cls, hero_name):
        """获取指定英雄的所有皮肤"""
        return cls.query.filter_by(hero_name=hero_name).order_by(cls.id).all()

    @classmethod
    def get_all_skins(cls):
        """获取所有皮肤"""
        return cls.query.order_by(cls.hero_name, cls.id).all()

    def to_dict(self):
        return {
            'id': self.id,
            'hero_name': self.hero_name,
            'name': self.name,
            'image_id': self.image_id,
            'image': generate_skin_image_url(self.image_id, self.image)
        }
    
    def get_image_url(self):
        """获取完整的皮肤图片URL"""
        return generate_skin_image_url(self.image_id, self.image)


class SkinOwnership(db.Model):
    """皮肤拥有记录表"""
    __tablename__ = 'skin_ownership'

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    region_id = db.Column(db.Integer, db.ForeignKey('regions.id'), nullable=False)
    skin_id = db.Column(db.Integer, db.ForeignKey('skins.id'), nullable=False)
    obtained_at = db.Column(db.DateTime, default=datetime.now)

    # 关系
    account = db.relationship('Account', backref='skin_ownerships', lazy=True)
    region = db.relationship('Region', backref='skin_ownerships', lazy=True)

    # 联合唯一约束
    __table_args__ = (
        db.UniqueConstraint('account_id', 'region_id', 'skin_id', name='unique_skin_ownership'),
    )

    @classmethod
    def get_owned_skins(cls, account_id, region_id):
        """获取指定区服已拥有的皮肤ID列表"""
        records = cls.query.filter_by(account_id=account_id, region_id=region_id).all()
        return [record.skin_id for record in records]

    @classmethod
    def get_skin_stats(cls, account_id, region_id):
        """获取皮肤统计信息"""
        owned_skin_ids = cls.get_owned_skins(account_id, region_id)
        all_skins = Skin.query.all()
        total = len(all_skins)
        owned = len(owned_skin_ids)

        # 按英雄统计
        by_hero = {}
        for skin in all_skins:
            if skin.hero_name not in by_hero:
                by_hero[skin.hero_name] = {'total': 0, 'owned': 0}
            by_hero[skin.hero_name]['total'] += 1
            if skin.id in owned_skin_ids:
                by_hero[skin.hero_name]['owned'] += 1

        return {
            'total': total,
            'owned': owned,
            'percentage': round((owned / total * 100)) if total > 0 else 0,
            'byHero': by_hero
        }

    @classmethod
    def toggle_skin(cls, account_id, region_id, skin_id, owned):
        """切换皮肤拥有状态"""
        existing = cls.query.filter_by(
            account_id=account_id,
            region_id=region_id,
            skin_id=skin_id
        ).first()

        if owned and not existing:
            # 添加拥有的皮肤
            ownership = cls(
                account_id=account_id,
                region_id=region_id,
                skin_id=skin_id
            )
            db.session.add(ownership)
            db.session.commit()
            return True
        elif not owned and existing:
            # 移除拥有的皮肤
            db.session.delete(existing)
            db.session.commit()
            return True
        return False

    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'region_id': self.region_id,
            'skin_id': self.skin_id,
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
    file_type = db.Column(db.String(20), default='json')  # json / database
    description = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    def get_absolute_path(self):
        """获取绝对路径"""
        from .config import BASE_DIR
        import os
        # 如果已经是绝对路径，直接返回
        if os.path.isabs(self.filepath):
            return self.filepath
        # 否则拼接为绝对路径
        return os.path.join(BASE_DIR, self.filepath)
    
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
            'file_type': self.file_type,
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
    
    # 加载皮肤数据
    skins = load_hero_skins_from_json()
    
    # 检查是否已有皮肤数据
    if Skin.query.count() == 0 and skins:
        print(f"初始化 {len(skins)} 个皮肤数据...")
        
        # 去重处理
        seen_skins = set()
        unique_skins = []
        
        for skin_data in skins:
            key = (skin_data['hero_name'], skin_data['name'])
            if key not in seen_skins:
                seen_skins.add(key)
                unique_skins.append(skin_data)
        
        if len(unique_skins) < len(skins):
            print(f"  发现并移除 {len(skins) - len(unique_skins)} 个重复皮肤")
        
        # 批量插入皮肤
        for skin_data in unique_skins:
            skin = Skin(
                hero_name=skin_data['hero_name'],
                name=skin_data['name'],
                image_id=skin_data.get('image_id', ''),
                image=skin_data.get('image', '')
            )
            db.session.add(skin)
        print(f"皮肤数据初始化完成: {len(unique_skins)} 个皮肤")
    
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


def get_user_collection(user_id):
    """
    获取用户所有账号所有区服的英雄和皮肤收藏（去重）
    
    Args:
        user_id: 用户ID
        
    Returns:
        dict: 包含英雄和皮肤收藏信息的字典
    """
    # 获取用户的所有账号
    accounts = Account.query.filter_by(user_id=user_id).all()
    
    # 获取所有英雄和皮肤数据
    all_heroes = Hero.query.all()
    all_skins = Skin.query.all()
    
    # 存储去重后的英雄和皮肤
    owned_hero_names = set()
    owned_skin_ids = set()
    
    # 存储英雄来源信息（哪些账号哪些区服拥有）
    hero_sources = {}
    # 存储皮肤来源信息（哪些账号哪些区服拥有）
    skin_sources = {}
    
    for account in accounts:
        # 获取该账号的所有区服
        regions = Region.query.filter_by(account_id=account.id).all()
        
        for region in regions:
            # 收集英雄拥有信息
            hero_ownerships = HeroOwnership.query.filter_by(
                account_id=account.id,
                region_id=region.id
            ).all()
            
            for ownership in hero_ownerships:
                hero_name = ownership.hero_name
                owned_hero_names.add(hero_name)
                
                # 记录来源
                if hero_name not in hero_sources:
                    hero_sources[hero_name] = []
                hero_sources[hero_name].append({
                    'account_id': account.id,
                    'account_name': account.name,
                    'region_id': region.id,
                    'region_name': region.name
                })
            
            # 收集皮肤拥有信息
            skin_ownerships = SkinOwnership.query.filter_by(
                account_id=account.id,
                region_id=region.id
            ).all()
            
            for ownership in skin_ownerships:
                skin_id = ownership.skin_id
                owned_skin_ids.add(skin_id)
                
                # 记录来源
                if skin_id not in skin_sources:
                    skin_sources[skin_id] = []
                skin_sources[skin_id].append({
                    'account_id': account.id,
                    'account_name': account.name,
                    'region_id': region.id,
                    'region_name': region.name
                })
    
    # 构建返回数据
    hero_images = get_hero_images()
    
    # 英雄列表，扁平化，已拥有的排在前面
    heroes_list = []
    for hero in all_heroes:
        heroes_list.append({
            'name': hero.name,
            'role': hero.role,
            'image': hero_images.get(hero.name, {}).get('image', ''),
            'url': hero_images.get(hero.name, {}).get('url', ''),
            'is_owned': hero.name in owned_hero_names,
            'sources': hero_sources.get(hero.name, [])
        })
    # 排序：已拥有的排在前面，已拥有的内部按拼音排序，未拥有的也按拼音排序
    from pypinyin import lazy_pinyin
    heroes_list.sort(key=lambda x: (0 if x['is_owned'] else 1, lazy_pinyin(x['name'])))
    
    # 按职业组织皮肤
    skins_by_hero = {}
    for hero in all_heroes:
        hero_skins = Skin.get_skins_by_hero(hero.name)
        if hero_skins:
            skins_by_hero[hero.name] = {
                'hero_image': hero_images.get(hero.name, {}).get('image', ''),
                'skins': [],
                'total': 0,
                'owned': 0
            }
            for skin in hero_skins:
                skins_by_hero[hero.name]['total'] += 1
                if skin.id in owned_skin_ids:
                    skins_by_hero[hero.name]['owned'] += 1
                skins_by_hero[hero.name]['skins'].append({
                    'id': skin.id,
                    'name': skin.name,
                    'image': skin.get_image_url(),
                    'is_owned': skin.id in owned_skin_ids,
                    'sources': skin_sources.get(skin.id, [])
                })
    
    # 统计总数据
    total_heroes = len(all_heroes)
    total_skins = len(all_skins)
    owned_hero_count = len(owned_hero_names)
    owned_skin_count = len(owned_skin_ids)
    
    return {
        'heroes_list': heroes_list,
        'skins_by_hero': skins_by_hero,
        'total_heroes': total_heroes,
        'owned_hero_count': owned_hero_count,
        'hero_percentage': round((owned_hero_count / total_heroes * 100)) if total_heroes > 0 else 0,
        'total_skins': total_skins,
        'owned_skin_count': owned_skin_count,
        'skin_percentage': round((owned_skin_count / total_skins * 100)) if total_skins > 0 else 0
    }
