"""
数据库迁移工具
用于将旧版本数据库迁移到新版本
"""
import sqlite3
import os
from datetime import datetime
import shutil
from models import db, User, Account, Region, HeroOwnership, SkinOwnership, Hero, Skin


class DatabaseMigration:
    """数据库迁移类"""
    
    def __init__(self, old_db_path):
        """
        初始化迁移器
        
        Args:
            old_db_path: 旧数据库文件路径
        """
        self.old_db_path = old_db_path
        self.errors = []
        self.warnings = []
        self.stats = {
            'users': 0,
            'accounts': 0,
            'regions': 0,
            'hero_ownerships': 0,
            'skin_ownerships': 0,
            'skins': 0
        }
        # ID映射表：旧ID -> 新ID
        self.user_id_mapping = {}  # { old_user_id: new_user_id }
        self.account_id_mapping = {}  # { old_account_id: new_account_id }
        self.region_id_mapping = {}  # { old_region_id: new_region_id }
        self.skin_id_mapping = {}  # { old_skin_id: new_skin_id }
    
    def validate_old_database(self):
        """
        验证旧数据库是否有效
        
        Returns:
            dict: 验证结果
        """
        result = {
            'valid': False,
            'message': '',
            'tables': []
        }
        
        try:
            if not os.path.exists(self.old_db_path):
                result['message'] = '数据库文件不存在'
                return result
            
            conn = sqlite3.connect(self.old_db_path)
            cursor = conn.cursor()
            
            # 获取所有表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            result['tables'] = tables
            
            # 检查必要的表是否存在
            required_tables = ['users', 'accounts', 'regions', 'hero_ownership']
            missing_tables = [t for t in required_tables if t not in tables]
            
            if missing_tables:
                result['message'] = f'缺少必要的表: {", ".join(missing_tables)}'
            else:
                result['valid'] = True
                result['message'] = '数据库验证通过'
                
                # 获取数据统计
                for table in required_tables:
                    cursor.execute(f'SELECT COUNT(*) FROM {table}')
                    count = cursor.fetchone()[0]
                    result[f'{table}_count'] = count
            
            # 检查可选表
            if 'skins' in tables:
                cursor.execute('SELECT COUNT(*) FROM skins')
                result['skins_count'] = cursor.fetchone()[0]
            
            if 'skin_ownership' in tables:
                cursor.execute('SELECT COUNT(*) FROM skin_ownership')
                result['skin_ownership_count'] = cursor.fetchone()[0]
            
            conn.close()
            return result
            
        except Exception as e:
            result['message'] = f'验证失败: {str(e)}'
            return result
    
    def migrate_data(self, app, mode='merge'):
        """
        迁移数据
        
        Args:
            app: Flask应用实例
            mode: 迁移模式
                - 'merge': 合并模式（保留现有数据，只添加新的）
                - 'replace': 替换模式（删除所有用户数据，完全使用旧数据）
        
        Returns:
            dict: 迁移结果
        """
        result = {
            'success': False,
            'message': '',
            'stats': {},
            'errors': []
        }
        
        try:
            # 连接到旧数据库
            old_conn = sqlite3.connect(self.old_db_path)
            old_cursor = old_conn.cursor()
            
            # 获取旧数据库中的表
            old_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            old_tables = [row[0] for row in old_cursor.fetchall()]
            
            # 在应用上下文中执行迁移
            with app.app_context():
                db.create_all()
                
                # 清空现有用户数据（如果是替换模式）
                if mode == 'replace':
                    self._clear_user_data()
                
                # 迁移用户数据
                users_migrated = self._migrate_users(old_conn, old_cursor)
                self.stats['users'] = users_migrated
                
                # 迁移账号数据
                accounts_migrated = self._migrate_accounts(old_conn, old_cursor)
                self.stats['accounts'] = accounts_migrated
                
                # 迁移区服数据
                regions_migrated = self._migrate_regions(old_conn, old_cursor)
                self.stats['regions'] = regions_migrated
                
                # 迁移英雄拥有记录
                hero_ownerships_migrated = self._migrate_hero_ownerships(old_conn, old_cursor)
                self.stats['hero_ownerships'] = hero_ownerships_migrated
                
                # 迁移皮肤表（如果存在）
                if 'skins' in old_tables:
                    skins_migrated = self._migrate_skins(old_conn, old_cursor)
                    self.stats['skins'] = skins_migrated
                
                # 迁移皮肤拥有记录（如果存在）
                if 'skin_ownership' in old_tables:
                    skin_ownerships_migrated = self._migrate_skin_ownerships(old_conn, old_cursor)
                    self.stats['skin_ownerships'] = skin_ownerships_migrated
                
                db.session.commit()
                
                result['success'] = True
                result['message'] = '数据迁移成功'
                result['stats'] = self.stats.copy()
                
            old_conn.close()
            return result
            
        except Exception as e:
            result['message'] = f'迁移失败: {str(e)}'
            result['errors'] = self.errors.copy()
            db.session.rollback()
            return result
    
    def _clear_user_data(self):
        """清空现有用户数据（保留英雄和皮肤基础数据）"""
        try:
            # 按依赖顺序删除
            SkinOwnership.query.delete()
            HeroOwnership.query.delete()
            Region.query.delete()
            Account.query.delete()
            # 不删除User表，因为我们可能想保留管理员账户
            # User.query.delete()
        except Exception as e:
            self.warnings.append(f'清空数据时出错: {str(e)}')
    
    def _migrate_users(self, old_conn, old_cursor):
        """迁移用户数据"""
        try:
            # 检查users表结构
            old_cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in old_cursor.fetchall()]
            
            # 根据表结构选择要查询的字段
            select_fields = []
            for field in ['id', 'username', 'password_hash', 'is_admin', 'created_at']:
                if field in columns:
                    select_fields.append(field)
            
            if not select_fields:
                self.warnings.append('users表缺少必要字段')
                return 0
            
            old_cursor.execute(f'SELECT {", ".join(select_fields)} FROM users')
            users = old_cursor.fetchall()
            
            migrated = 0
            for user_data in users:
                try:
                    old_id_idx = select_fields.index('id')
                    old_user_id = user_data[old_id_idx]
                    
                    # 检查是否已存在（根据用户名）
                    username_idx = select_fields.index('username')
                    username = user_data[username_idx]
                    existing = User.query.filter_by(username=username).first()
                    
                    if existing:
                        # 用户已存在，保存ID映射
                        self.user_id_mapping[old_user_id] = existing.id
                    else:
                        user = User()
                        for i, field in enumerate(select_fields):
                            value = user_data[i]
                            if field == 'id':
                                continue  # 跳过id，让数据库自动生成
                            elif field == 'username':
                                user.username = value
                            elif field == 'password_hash':
                                user.password_hash = value
                            elif field == 'is_admin':
                                user.is_admin = bool(value) if value is not None else False
                            elif field == 'created_at':
                                if value:
                                    try:
                                        user.created_at = datetime.fromisoformat(value.replace('Z', '+00:00'))
                                    except:
                                        user.created_at = datetime.now()
                        
                        db.session.add(user)
                        db.session.flush()
                        # 保存ID映射
                        self.user_id_mapping[old_user_id] = user.id
                        migrated += 1
                except Exception as e:
                    self.errors.append(f'迁移用户 {user_data} 时出错: {str(e)}')
            
            return migrated
        except Exception as e:
            self.errors.append(f'迁移用户数据时出错: {str(e)}')
            return 0
    
    def _migrate_accounts(self, old_conn, old_cursor):
        """迁移账号数据"""
        try:
            # 检查accounts表结构
            old_cursor.execute("PRAGMA table_info(accounts)")
            columns = [col[1] for col in old_cursor.fetchall()]
            
            # 根据表结构选择要查询的字段
            select_fields = []
            for field in ['id', 'user_id', 'name', 'login_type', 'platform', 'sort_order', 'created_at']:
                if field in columns:
                    select_fields.append(field)
            
            if not select_fields:
                self.warnings.append('accounts表缺少必要字段')
                return 0
            
            old_cursor.execute(f'SELECT {", ".join(select_fields)} FROM accounts')
            accounts = old_cursor.fetchall()
            
            migrated = 0
            for account_data in accounts:
                try:
                    old_id_idx = select_fields.index('id')
                    old_account_id = account_data[old_id_idx]
                    
                    # 获取user_id
                    user_id_idx = select_fields.index('user_id')
                    old_user_id = account_data[user_id_idx]
                    
                    # 使用ID映射找到新的user_id
                    new_user_id = self.user_id_mapping.get(old_user_id)
                    if not new_user_id:
                        self.warnings.append(f'账号ID {old_account_id} 的用户ID {old_user_id} 未找到映射，跳过')
                        continue
                    
                    # 检查是否已存在同名账号
                    name_idx = select_fields.index('name')
                    name = account_data[name_idx]
                    existing = Account.query.filter_by(user_id=new_user_id, name=name).first()
                    
                    if existing:
                        # 账号已存在，保存ID映射
                        self.account_id_mapping[old_account_id] = existing.id
                    else:
                        account = Account()
                        account.user_id = new_user_id
                        
                        for i, field in enumerate(select_fields):
                            value = account_data[i]
                            if field == 'id':
                                continue
                            elif field == 'user_id':
                                continue
                            elif field == 'name':
                                account.name = value
                            elif field == 'login_type':
                                account.login_type = value if value else 'qq'
                            elif field == 'platform':
                                account.platform = value if value else 'android'
                            elif field == 'sort_order':
                                account.sort_order = value if value else 0
                            elif field == 'created_at':
                                if value:
                                    try:
                                        account.created_at = datetime.fromisoformat(value.replace('Z', '+00:00'))
                                    except:
                                        account.created_at = datetime.now()
                        
                        db.session.add(account)
                        db.session.flush()  # 获取新id
                        self.account_id_mapping[old_account_id] = account.id
                        migrated += 1
                except Exception as e:
                    self.errors.append(f'迁移账号 {account_data} 时出错: {str(e)}')
            
            return migrated
        except Exception as e:
            self.errors.append(f'迁移账号数据时出错: {str(e)}')
            return 0
    
    def _migrate_regions(self, old_conn, old_cursor):
        """迁移区服数据"""
        try:
            # 检查regions表结构
            old_cursor.execute("PRAGMA table_info(regions)")
            columns = [col[1] for col in old_cursor.fetchall()]
            
            # 根据表结构选择要查询的字段
            select_fields = []
            for field in ['id', 'account_id', 'name', 'sort_order', 'created_at']:
                if field in columns:
                    select_fields.append(field)
            
            if not select_fields:
                self.warnings.append('regions表缺少必要字段')
                return 0
            
            old_cursor.execute(f'SELECT {", ".join(select_fields)} FROM regions')
            regions = old_cursor.fetchall()
            
            migrated = 0
            for region_data in regions:
                try:
                    old_id_idx = select_fields.index('id')
                    old_region_id = region_data[old_id_idx]
                    
                    # 获取account_id
                    account_id_idx = select_fields.index('account_id')
                    old_account_id = region_data[account_id_idx]
                    
                    # 使用ID映射找到新的account_id
                    new_account_id = self.account_id_mapping.get(old_account_id)
                    if not new_account_id:
                        self.warnings.append(f'区服ID {old_region_id} 的账号ID {old_account_id} 未找到映射，跳过')
                        continue
                    
                    # 检查是否已存在同名区服
                    name_idx = select_fields.index('name')
                    name = region_data[name_idx]
                    existing = Region.query.filter_by(account_id=new_account_id, name=name).first()
                    
                    if existing:
                        # 区服已存在，保存ID映射
                        self.region_id_mapping[old_region_id] = existing.id
                    else:
                        region = Region()
                        region.account_id = new_account_id
                        
                        for i, field in enumerate(select_fields):
                            value = region_data[i]
                            if field == 'id':
                                continue
                            elif field == 'account_id':
                                continue
                            elif field == 'name':
                                region.name = value
                            elif field == 'sort_order':
                                region.sort_order = value if value else 0
                            elif field == 'created_at':
                                if value:
                                    try:
                                        region.created_at = datetime.fromisoformat(value.replace('Z', '+00:00'))
                                    except:
                                        region.created_at = datetime.now()
                        
                        db.session.add(region)
                        db.session.flush()
                        self.region_id_mapping[old_region_id] = region.id
                        migrated += 1
                except Exception as e:
                    self.errors.append(f'迁移区服 {region_data} 时出错: {str(e)}')
            
            return migrated
        except Exception as e:
            self.errors.append(f'迁移区服数据时出错: {str(e)}')
            return 0
    
    def _migrate_hero_ownerships(self, old_conn, old_cursor):
        """迁移英雄拥有记录"""
        try:
            # 检查hero_ownership表结构
            old_cursor.execute("PRAGMA table_info(hero_ownership)")
            columns = [col[1] for col in old_cursor.fetchall()]
            
            # 根据表结构选择要查询的字段
            select_fields = []
            for field in ['id', 'account_id', 'region_id', 'hero_name', 'obtained_at']:
                if field in columns:
                    select_fields.append(field)
            
            if not select_fields:
                self.warnings.append('hero_ownership表缺少必要字段')
                return 0
            
            old_cursor.execute(f'SELECT {", ".join(select_fields)} FROM hero_ownership')
            ownerships = old_cursor.fetchall()
            
            migrated = 0
            for ownership_data in ownerships:
                try:
                    # 获取字段值
                    account_id_idx = select_fields.index('account_id')
                    region_id_idx = select_fields.index('region_id')
                    hero_name_idx = select_fields.index('hero_name')
                    
                    old_account_id = ownership_data[account_id_idx]
                    old_region_id = ownership_data[region_id_idx]
                    hero_name = ownership_data[hero_name_idx]
                    
                    # 使用ID映射找到新的account_id和region_id
                    new_account_id = self.account_id_mapping.get(old_account_id)
                    new_region_id = self.region_id_mapping.get(old_region_id)
                    
                    if not new_account_id:
                        self.warnings.append(f'英雄拥有记录的账号ID {old_account_id} 未找到映射，跳过')
                        continue
                    
                    if not new_region_id:
                        self.warnings.append(f'英雄拥有记录的区服ID {old_region_id} 未找到映射，跳过')
                        continue
                    
                    # 验证英雄是否存在
                    hero = Hero.query.filter_by(name=hero_name).first()
                    if not hero:
                        self.warnings.append(f'英雄 {hero_name} 不存在，跳过')
                        continue
                    
                    # 检查是否已存在
                    existing = HeroOwnership.query.filter_by(
                        account_id=new_account_id,
                        region_id=new_region_id,
                        hero_name=hero_name
                    ).first()
                    
                    if not existing:
                        ownership = HeroOwnership()
                        ownership.account_id = new_account_id
                        ownership.region_id = new_region_id
                        ownership.hero_name = hero_name
                        
                        # 设置获取时间
                        obtained_at_idx = select_fields.index('obtained_at')
                        obtained_at = ownership_data[obtained_at_idx]
                        if obtained_at:
                            try:
                                ownership.obtained_at = datetime.fromisoformat(obtained_at.replace('Z', '+00:00'))
                            except:
                                ownership.obtained_at = datetime.now()
                        
                        db.session.add(ownership)
                        migrated += 1
                except Exception as e:
                    self.errors.append(f'迁移英雄拥有记录时出错: {str(e)}')
            
            return migrated
        except Exception as e:
            self.errors.append(f'迁移英雄拥有记录时出错: {str(e)}')
            return 0
    
    def _migrate_skins(self, old_conn, old_cursor):
        """迁移皮肤数据"""
        try:
            old_cursor.execute("PRAGMA table_info(skins)")
            columns = [col[1] for col in old_cursor.fetchall()]
            
            # 根据表结构选择要查询的字段
            select_fields = []
            for field in ['id', 'hero_name', 'name', 'image_id', 'image']:
                if field in columns:
                    select_fields.append(field)
            
            if not select_fields:
                self.warnings.append('skins表缺少必要字段')
                return 0
            
            old_cursor.execute(f'SELECT {", ".join(select_fields)} FROM skins')
            skins = old_cursor.fetchall()
            
            migrated = 0
            for skin_data in skins:
                try:
                    old_id_idx = select_fields.index('id')
                    old_skin_id = skin_data[old_id_idx]
                    
                    hero_name_idx = select_fields.index('hero_name')
                    name_idx = select_fields.index('name')
                    hero_name = skin_data[hero_name_idx]
                    name = skin_data[name_idx]
                    
                    # 验证英雄是否存在
                    hero = Hero.query.filter_by(name=hero_name).first()
                    if not hero:
                        self.warnings.append(f'英雄 {hero_name} 不存在，跳过皮肤 {name}')
                        continue
                    
                    # 检查是否已存在
                    existing = Skin.query.filter_by(hero_name=hero_name, name=name).first()
                    
                    if existing:
                        # 皮肤已存在，保存ID映射
                        self.skin_id_mapping[old_skin_id] = existing.id
                    else:
                        skin = Skin()
                        skin.hero_name = hero_name
                        skin.name = name
                        
                        for i, field in enumerate(select_fields):
                            value = skin_data[i]
                            if field == 'id':
                                continue
                            elif field == 'hero_name':
                                continue
                            elif field == 'name':
                                continue
                            elif field == 'image_id':
                                skin.image_id = value if value else ''
                            elif field == 'image':
                                skin.image = value if value else ''
                        
                        db.session.add(skin)
                        db.session.flush()
                        self.skin_id_mapping[old_skin_id] = skin.id
                        migrated += 1
                except Exception as e:
                    self.errors.append(f'迁移皮肤 {skin_data} 时出错: {str(e)}')
            
            return migrated
        except Exception as e:
            self.errors.append(f'迁移皮肤数据时出错: {str(e)}')
            return 0
    
    def _migrate_skin_ownerships(self, old_conn, old_cursor):
        """迁移皮肤拥有记录"""
        try:
            old_cursor.execute("PRAGMA table_info(skin_ownership)")
            columns = [col[1] for col in old_cursor.fetchall()]
            
            # 根据表结构选择要查询的字段
            select_fields = []
            for field in ['id', 'account_id', 'region_id', 'skin_id', 'obtained_at']:
                if field in columns:
                    select_fields.append(field)
            
            if not select_fields:
                self.warnings.append('skin_ownership表缺少必要字段')
                return 0
            
            old_cursor.execute(f'SELECT {", ".join(select_fields)} FROM skin_ownership')
            ownerships = old_cursor.fetchall()
            
            migrated = 0
            for ownership_data in ownerships:
                try:
                    account_id_idx = select_fields.index('account_id')
                    region_id_idx = select_fields.index('region_id')
                    skin_id_idx = select_fields.index('skin_id')
                    
                    old_account_id = ownership_data[account_id_idx]
                    old_region_id = ownership_data[region_id_idx]
                    old_skin_id = ownership_data[skin_id_idx]
                    
                    # 使用ID映射找到新的account_id、region_id和skin_id
                    new_account_id = self.account_id_mapping.get(old_account_id)
                    new_region_id = self.region_id_mapping.get(old_region_id)
                    new_skin_id = self.skin_id_mapping.get(old_skin_id)
                    
                    if not new_account_id:
                        self.warnings.append(f'皮肤拥有记录的账号ID {old_account_id} 未找到映射，跳过')
                        continue
                    
                    if not new_region_id:
                        self.warnings.append(f'皮肤拥有记录的区服ID {old_region_id} 未找到映射，跳过')
                        continue
                    
                    if not new_skin_id:
                        self.warnings.append(f'皮肤拥有记录的皮肤ID {old_skin_id} 未找到映射，跳过')
                        continue
                    
                    # 检查是否已存在
                    existing = SkinOwnership.query.filter_by(
                        account_id=new_account_id,
                        region_id=new_region_id,
                        skin_id=new_skin_id
                    ).first()
                    
                    if not existing:
                        ownership = SkinOwnership()
                        ownership.account_id = new_account_id
                        ownership.region_id = new_region_id
                        ownership.skin_id = new_skin_id
                        
                        # 设置获取时间
                        obtained_at_idx = select_fields.index('obtained_at')
                        obtained_at = ownership_data[obtained_at_idx]
                        if obtained_at:
                            try:
                                ownership.obtained_at = datetime.fromisoformat(obtained_at.replace('Z', '+00:00'))
                            except:
                                ownership.obtained_at = datetime.now()
                        
                        db.session.add(ownership)
                        migrated += 1
                except Exception as e:
                    self.errors.append(f'迁移皮肤拥有记录时出错: {str(e)}')
            
            return migrated
        except Exception as e:
            self.errors.append(f'迁移皮肤拥有记录时出错: {str(e)}')
            return 0


def migrate_from_old_database(app, old_db_path, mode='merge'):
    """
    从旧数据库迁移数据的便捷函数
    
    Args:
        app: Flask应用实例
        old_db_path: 旧数据库文件路径
        mode: 迁移模式 ('merge' 或 'replace')
    
    Returns:
        dict: 迁移结果
    """
    migration = DatabaseMigration(old_db_path)
    
    # 先验证
    validation = migration.validate_old_database()
    if not validation['valid']:
        return {
            'success': False,
            'message': validation['message'],
            'validation': validation
        }
    
    # 执行迁移
    return migration.migrate_data(app, mode)
