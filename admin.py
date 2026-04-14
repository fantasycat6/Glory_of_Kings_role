"""
管理后台蓝图 - 用户管理、英雄管理、备份管理
"""
from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash, Response, send_file, current_app
from flask_login import login_required, current_user
from functools import wraps
from models import db, User, Account, Region, Hero, HeroOwnership, BackupFile, load_heroes_from_json, load_hero_images_from_json
from config import BASE_DIR
import json
import os
from datetime import datetime
from pathlib import Path
import shutil

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            if request.is_json:
                return jsonify({'success': False, 'message': '需要管理员权限'}), 403
            flash('需要管理员权限', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== 管理后台主页 ====================

@admin_bp.route('/admin/')
@login_required
@admin_required
def index():
    """管理后台首页"""
    users = User.query.all()
    heroes = Hero.query.all()
    return render_template('admin/dashboard.html', users=users, heroes=heroes)


# ==================== 用户管理 ====================

@admin_bp.route('/admin/users')
@login_required
@admin_required
def users():
    """用户管理页面"""
    users = User.query.all()
    return render_template('admin/users.html', users=users, current_user=current_user)


@admin_bp.route('/api/admin/users', methods=['GET'])
@login_required
@admin_required
def api_get_users():
    """获取用户列表API"""
    users = User.query.all()
    return jsonify([user.to_dict() for user in users])


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['GET'])
@login_required
@admin_required
def api_get_user(user_id):
    """获取单个用户信息API"""
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())


@admin_bp.route('/api/admin/users', methods=['POST'])
@login_required
@admin_required
def api_create_user():
    """创建用户API"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    email = data.get('email', '').strip()
    is_admin = data.get('isAdmin', False)
    
    if not username or not password:
        return jsonify({'success': False, 'error': '用户名和密码不能为空'}), 400
    
    if len(password) < 6:
        return jsonify({'success': False, 'error': '密码长度至少6位'}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'error': '用户名已存在'}), 400
    
    user = User(username=username, email=email, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    return jsonify({'success': True, 'user': user.to_dict()})


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@login_required
@admin_required
def api_update_user(user_id):
    """更新用户API"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    is_admin = data.get('isAdmin')
    password = data.get('password', '')
    
    # 检查是否至少保留一个管理员
    if user.is_admin and not is_admin:
        admin_count = User.query.filter_by(is_admin=True).count()
        if admin_count <= 1:
            return jsonify({'success': False, 'error': '至少需要保留一个管理员'}), 400
    
    if username and username != user.username:
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'error': '用户名已存在'}), 400
        user.username = username
    
    if email is not None:
        user.email = email
    
    if is_admin is not None:
        user.is_admin = is_admin
    
    if password and len(password) >= 6:
        user.set_password(password)
    
    db.session.commit()
    return jsonify({'success': True, 'user': user.to_dict()})


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_user(user_id):
    """删除用户API"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        return jsonify({'success': False, 'error': '不能删除当前登录的账号'}), 400
    
    # 检查是否至少保留一个管理员
    if user.is_admin:
        admin_count = User.query.filter_by(is_admin=True).count()
        if admin_count <= 1:
            return jsonify({'success': False, 'error': '至少需要保留一个管理员'}), 400
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'success': True})


@admin_bp.route('/api/admin/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def api_reset_password(user_id):
    """重置用户密码API"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    password = data.get('password', '')
    
    if not password or len(password) < 6:
        return jsonify({'success': False, 'error': '密码长度至少6位'}), 400
    
    user.set_password(password)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '密码已重置'})


# ==================== 英雄管理 ====================

@admin_bp.route('/admin/heroes')
@login_required
@admin_required
def heroes():
    """英雄管理页面"""
    return render_template('admin/heroes.html')


@admin_bp.route('/api/admin/heroes', methods=['GET'])
@login_required
@admin_required
def api_get_heroes():
    """获取英雄列表API"""
    from pypinyin import pinyin, Style
    
    page = request.args.get('page', 1, type=int)
    role_filter = request.args.get('role', 'all')
    search_query = request.args.get('search', '')
    is_default_filter = request.args.get('isDefault', 'all')
    per_page = 10
    
    query = Hero.query
    
    # 筛选
    if role_filter != 'all':
        query = query.filter(Hero.role.like(f'%{role_filter}%'))
    
    if search_query:
        query = query.filter(Hero.name.like(f'%{search_query}%'))
    
    if is_default_filter != 'all':
        is_default = is_default_filter == 'true'
        query = query.filter_by(is_default=is_default)
    
    # 获取所有符合条件的英雄
    all_heroes = query.all()
    
    # 排序：默认英雄排前面，然后按拼音排序
    def get_pinyin_key(hero):
        try:
            pinyin_list = pinyin(hero.name, style=Style.NORMAL)
            return ''.join([p[0] for p in pinyin_list])
        except:
            return hero.name.lower()
    
    # 先按默认状态分组，再按拼音排序
    default_heroes = [h for h in all_heroes if h.is_default]
    non_default_heroes = [h for h in all_heroes if not h.is_default]
    
    default_heroes.sort(key=get_pinyin_key)
    non_default_heroes.sort(key=get_pinyin_key)
    
    sorted_heroes = default_heroes + non_default_heroes
    
    # 手动分页
    total = len(sorted_heroes)
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    paginated_heroes = sorted_heroes[start:end]
    
    default_hero_names = [h.name for h in Hero.get_default_heroes()]
    # 使用固定顺序的职业列表
    roles = ['坦克', '战士', '刺客', '法师', '射手', '辅助']
    hero_images = load_hero_images_from_json()
    
    return jsonify({
        'success': True,
        'heroes': [hero.to_dict() for hero in paginated_heroes],
        'allHeroes': [hero.to_dict() for hero in sorted_heroes],
        'defaultHeroNames': default_hero_names,
        'roles': roles,
        'heroImages': hero_images,
        'pagination': {
            'currentPage': page,
            'totalPages': max(1, total_pages),
            'totalHeroes': total,
            'perPage': per_page
        }
    })


@admin_bp.route('/api/admin/heroes', methods=['POST'])
@login_required
@admin_required
def api_create_hero():
    """添加英雄API"""
    data = request.get_json()
    name = data.get('name', '').strip()
    role = data.get('role', '').strip()
    is_default = data.get('isDefault', False)
    
    if not name or not role:
        return jsonify({'success': False, 'error': '英雄名称和职业不能为空'}), 400
    
    if Hero.query.get(name):
        return jsonify({'success': False, 'error': '英雄已存在'}), 400
    
    hero = Hero(name=name, role=role, is_default=is_default)
    db.session.add(hero)
    db.session.commit()
    
    return jsonify({'success': True, 'hero': hero.to_dict()})


@admin_bp.route('/api/admin/heroes/<hero_name>', methods=['PUT'])
@login_required
@admin_required
def api_update_hero(hero_name):
    """更新英雄API"""
    hero = Hero.query.get_or_404(hero_name)
    data = request.get_json()
    
    new_name = data.get('name', '').strip()
    role = data.get('role', '').strip()
    is_default = data.get('isDefault')
    
    # 如果修改了名称，检查新名称是否已存在
    if new_name and new_name != hero_name:
        if Hero.query.get(new_name):
            return jsonify({'success': False, 'error': '新名称的英雄已存在'}), 400
        
        # 创建新英雄记录
        new_hero = Hero(name=new_name, role=role or hero.role, is_default=is_default if is_default is not None else hero.is_default)
        db.session.add(new_hero)
        
        # 更新所有相关记录
        HeroOwnership.query.filter_by(hero_name=hero_name).update({'hero_name': new_name})
        
        # 删除旧英雄记录
        db.session.delete(hero)
        db.session.commit()
        
        return jsonify({'success': True, 'hero': new_hero.to_dict()})
    
    if role:
        hero.role = role
    if is_default is not None:
        hero.is_default = is_default
    
    db.session.commit()
    return jsonify({'success': True, 'hero': hero.to_dict()})


@admin_bp.route('/api/admin/heroes/<hero_name>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_hero(hero_name):
    """删除英雄API"""
    hero = Hero.query.get_or_404(hero_name)
    
    db.session.delete(hero)
    db.session.commit()
    
    return jsonify({'success': True})


@admin_bp.route('/api/admin/heroes/reset', methods=['POST'])
@login_required
@admin_required
def api_reset_heroes():
    """重置英雄数据API"""
    heroes_data, default_hero_names = load_heroes_from_json()
    
    # 清空现有英雄数据
    Hero.query.delete()
    
    # 重新导入
    for hero_data in heroes_data:
        hero = Hero(
            name=hero_data['name'],
            role=hero_data['role'],
            is_default=hero_data['name'] in default_hero_names
        )
        db.session.add(hero)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'英雄数据已重置: {len(heroes_data)} 位英雄',
        'heroes': len(heroes_data)
    })


# ==================== 备份管理 ====================

@admin_bp.route('/admin/backup')
@login_required
@admin_required
def backup():
    """备份管理页面"""
    return render_template('admin/backup.html')


@admin_bp.route('/api/admin/backup/export')
@login_required
@admin_required
def api_export_backup():
    """导出备份"""
    heroes = [hero.to_dict() for hero in Hero.query.order_by(Hero.name).all()]
    default_heroes = [h.name for h in Hero.get_default_heroes()]
    
    backup_data = {
        'version': '1.0',
        'exported_at': datetime.now().isoformat(),
        'heroes': heroes,
        'default_heroes': default_heroes
    }
    
    filename = f"wzry_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    return Response(
        json.dumps(backup_data, ensure_ascii=False, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@admin_bp.route('/api/admin/backup/create', methods=['POST'])
@login_required
@admin_required
def api_create_backup():
    """创建备份"""
    heroes = [hero.to_dict() for hero in Hero.query.order_by(Hero.name).all()]
    default_heroes = [h.name for h in Hero.get_default_heroes()]
    
    backup_data = {
        'version': '1.0',
        'exported_at': datetime.now().isoformat(),
        'heroes': heroes,
        'default_heroes': default_heroes
    }
    
    # 确保备份目录存在
    backup_dir = Path(__file__).parent / 'backup'
    backup_dir.mkdir(exist_ok=True)
    
    filename = f"wzry_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = backup_dir / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    
    # 记录到数据库（使用相对路径）
    relative_path = os.path.join('backup', filename)
    backup_record = BackupFile(
        filename=filename,
        filepath=relative_path,
        file_size=os.path.getsize(filepath),
        backup_type='manual',
        file_type='json',
        description='英雄数据备份'
    )
    db.session.add(backup_record)
    db.session.commit()
    
    return jsonify({'success': True, 'filename': filename, 'backup': backup_record.to_dict()})


@admin_bp.route('/api/admin/backup/import', methods=['POST'])
@login_required
@admin_required
def api_import_backup():
    """导入备份"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '请求数据为空'}), 400
        
        backup_data = data.get('data')
        mode = data.get('mode', 'merge')  # merge or overwrite
        
        if not backup_data or not isinstance(backup_data, dict) or 'heroes' not in backup_data:
            return jsonify({'success': False, 'error': '无效的备份文件格式'}), 400
        
        heroes = backup_data['heroes']
        default_heroes = backup_data.get('default_heroes', [])
        
        imported = 0
        skipped = 0
        errors = 0
        
        # 覆盖模式：先备份用户拥有记录并清空表
        ownership_backup = []
        if mode == 'overwrite':
            ownership_backup = [
                {
                    'account_id': o.account_id,
                    'region_id': o.region_id,
                    'hero_name': o.hero_name
                }
                for o in HeroOwnership.query.all()
            ]
            HeroOwnership.query.delete()
            Hero.query.delete()
            db.session.commit()
        
        # 收集备份中已有的英雄名称，避免重复查询
        existing_hero_names = set()
        if mode != 'overwrite':
            existing_hero_names = {h.name for h in Hero.query.all()}
        
        for hero_data in heroes:
            try:
                if not hero_data.get('name') or not hero_data.get('role'):
                    errors += 1
                    continue
                
                hero_name = hero_data['name']
                
                # 非覆盖模式：检查是否已存在
                if mode != 'overwrite' and hero_name in existing_hero_names:
                    skipped += 1
                    continue
                
                hero = Hero(
                    name=hero_name,
                    role=hero_data['role'],
                    is_default=hero_name in default_heroes
                )
                db.session.add(hero)
                imported += 1
            except Exception as e:
                print(f"导入英雄错误: {hero_data.get('name')}, {e}")
                errors += 1
        
        db.session.commit()
        
        # 恢复用户拥有记录（过滤掉已删除的英雄）
        restored = 0
        skipped_ownerships = 0
        if mode == 'overwrite' and ownership_backup:
            new_hero_names = {h.name for h in Hero.query.all()}
            # 获取现有的ownership记录用于查重
            existing_ownerships = set()
            for o in HeroOwnership.query.all():
                existing_ownerships.add((o.account_id, o.region_id, o.hero_name))
            
            for ownership_data in ownership_backup:
                if ownership_data['hero_name'] in new_hero_names:
                    key = (ownership_data['account_id'], ownership_data['region_id'], ownership_data['hero_name'])
                    if key not in existing_ownerships:
                        new_ownership = HeroOwnership(
                            account_id=ownership_data['account_id'],
                            region_id=ownership_data['region_id'],
                            hero_name=ownership_data['hero_name']
                        )
                        db.session.add(new_ownership)
                        restored += 1
                    else:
                        skipped_ownerships += 1
            db.session.commit()
        
        message = f'导入完成：成功 {imported} 个英雄，跳过 {skipped} 个，失败 {errors} 个'
        if restored > 0:
            message += f'，恢复 {restored} 条用户记录'
        if skipped_ownerships > 0:
            message += f'，跳过 {skipped_ownerships} 条重复记录'
        
        return jsonify({
            'success': True,
            'message': message,
            'imported': imported,
            'skipped': skipped,
            'errors': errors,
            'restored': restored
        })
    except Exception as e:
        db.session.rollback()
        print(f"导入备份错误: {e}")
        return jsonify({'success': False, 'error': f'导入失败: {str(e)}'}), 500


@admin_bp.route('/api/admin/backup/list', methods=['GET'])
@login_required
@admin_required
def api_list_backups():
    """获取备份列表"""
    backups = BackupFile.query.order_by(BackupFile.created_at.desc()).all()
    return jsonify({'success': True, 'backups': [b.to_dict() for b in backups]})


@admin_bp.route('/api/admin/backup/download/<int:backup_id>')
@login_required
@admin_required
def api_download_backup(backup_id):
    """下载备份文件"""
    backup = BackupFile.query.get_or_404(backup_id)
    abs_path = backup.get_absolute_path()
    
    if not os.path.exists(abs_path):
        return jsonify({'success': False, 'error': '备份文件不存在'}), 404
    
    return send_file(
        abs_path,
        as_attachment=True,
        download_name=backup.filename,
        mimetype='application/json'
    )


@admin_bp.route('/api/admin/backup/restore/<int:backup_id>', methods=['POST'])
@login_required
@admin_required
def api_restore_backup(backup_id):
    """恢复备份"""
    try:
        backup = BackupFile.query.get_or_404(backup_id)
        abs_path = backup.get_absolute_path()

        if not os.path.exists(abs_path):
            return jsonify({'success': False, 'error': '备份文件不存在'}), 404

        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
        except Exception as e:
            return jsonify({'success': False, 'error': f'备份文件解析失败: {e}'}), 400

        if 'heroes' not in backup_data:
            return jsonify({'success': False, 'error': '无效的备份文件格式'}), 400

        mode = 'overwrite'
        if request.is_json:
            mode = request.json.get('mode', 'overwrite')
        
        heroes = backup_data['heroes']
        default_heroes = backup_data.get('default_heroes', [])
        
        imported = 0
        skipped = 0
        errors = 0
        
        # 覆盖模式：先备份用户拥有记录并清空表
        ownership_backup = []
        if mode == 'overwrite':
            ownership_backup = [
                {
                    'account_id': o.account_id,
                    'region_id': o.region_id,
                    'hero_name': o.hero_name
                }
                for o in HeroOwnership.query.all()
            ]
            HeroOwnership.query.delete()
            Hero.query.delete()
            db.session.commit()
        
        # 收集备份中已有的英雄名称，避免重复查询
        existing_hero_names = set()
        if mode != 'overwrite':
            existing_hero_names = {h.name for h in Hero.query.all()}
        
        for hero_data in heroes:
            try:
                if not hero_data.get('name') or not hero_data.get('role'):
                    errors += 1
                    continue
                
                hero_name = hero_data['name']
                
                # 非覆盖模式：检查是否已存在
                if mode != 'overwrite' and hero_name in existing_hero_names:
                    skipped += 1
                    continue
                
                hero = Hero(
                    name=hero_name,
                    role=hero_data['role'],
                    is_default=hero_name in default_heroes
                )
                db.session.add(hero)
                imported += 1
            except Exception as e:
                print(f"恢复英雄错误: {hero_data.get('name')}, {e}")
                errors += 1
        
        db.session.commit()
        
        # 恢复用户拥有记录（检查重复）
        restored = 0
        skipped_ownerships = 0
        if mode == 'overwrite' and ownership_backup:
            # 获取新导入的英雄名称集合
            new_hero_names = {h.name for h in Hero.query.all()}
            # 获取现有的ownership记录用于查重（此时应该为空，因为已经删除了）
            existing_ownerships = set()
            for o in HeroOwnership.query.all():
                existing_ownerships.add((o.account_id, o.region_id, o.hero_name))
            
            for ownership_data in ownership_backup:
                if ownership_data['hero_name'] in new_hero_names:
                    key = (ownership_data['account_id'], ownership_data['region_id'], ownership_data['hero_name'])
                    if key not in existing_ownerships:
                        new_ownership = HeroOwnership(
                            account_id=ownership_data['account_id'],
                            region_id=ownership_data['region_id'],
                            hero_name=ownership_data['hero_name']
                        )
                        db.session.add(new_ownership)
                        restored += 1
                    else:
                        skipped_ownerships += 1
            db.session.commit()
        
        message = f'恢复完成：成功 {imported} 个英雄，跳过 {skipped} 个，失败 {errors} 个'
        if restored > 0:
            message += f'，恢复 {restored} 条用户记录'
        if skipped_ownerships > 0:
            message += f'，跳过 {skipped_ownerships} 条重复记录'
        
        return jsonify({
            'success': True,
            'message': message,
            'imported': imported,
            'skipped': skipped,
            'errors': errors,
            'restored': restored
        })
    except Exception as e:
        db.session.rollback()
        print(f"恢复备份错误: {e}")
        return jsonify({'success': False, 'error': f'恢复失败: {str(e)}'}), 500


@admin_bp.route('/api/admin/backup/<int:backup_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_backup(backup_id):
    """删除备份"""
    backup = BackupFile.query.get(backup_id)
    
    # 如果记录不存在，可能是已经被删除了，返回成功
    if not backup:
        return jsonify({'success': True, 'message': '备份已删除'})
    
    # 删除文件
    abs_path = backup.get_absolute_path()
    if os.path.exists(abs_path):
        try:
            os.remove(abs_path)
        except Exception as e:
            return jsonify({'success': False, 'error': f'删除文件失败: {e}'}), 500
    
    # 从数据库删除记录
    db.session.delete(backup)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '备份已删除'})


@admin_bp.route('/api/admin/backup/scan', methods=['POST'])
@login_required
@admin_required
def api_scan_backups():
    """扫描备份文件夹，同步到数据库"""
    try:
        backup_dir = os.path.join(BASE_DIR, 'backup')
        if not os.path.exists(backup_dir):
            return jsonify({'success': True, 'message': '备份目录不存在', 'added': 0})
        
        # 获取数据库中已有的备份文件名
        existing_files = {b.filename for b in BackupFile.query.all()}
        
        added_count = 0
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
                added_count += 1
            except Exception as e:
                print(f"扫描备份文件失败 {filename}: {e}")
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'扫描完成，新增 {added_count} 个备份文件',
            'added': added_count
        })
    except Exception as e:
        db.session.rollback()
        print(f"扫描备份文件错误: {e}")
        return jsonify({'success': False, 'error': f'扫描失败: {str(e)}'}), 500


@admin_bp.route('/api/admin/backup/cleanup-auto', methods=['POST'])
@login_required
@admin_required
def api_cleanup_auto_backups():
    """清理旧的自动备份，只保留最近5个"""
    try:
        # 获取所有自动备份，按时间倒序
        auto_backups = BackupFile.query.filter_by(backup_type='auto').order_by(BackupFile.created_at.desc()).all()
        
        # 只保留最近5个
        keep_count = 5
        if len(auto_backups) <= keep_count:
            return jsonify({
                'success': True, 
                'message': f'自动备份数量 ({len(auto_backups)}) 未超过限制 ({keep_count})，无需清理',
                'deleted': 0
            })
        
        # 删除旧的自动备份
        deleted_count = 0
        for backup in auto_backups[keep_count:]:
            # 删除文件
            abs_path = backup.get_absolute_path()
            if os.path.exists(abs_path):
                try:
                    os.remove(abs_path)
                except Exception as e:
                    print(f"删除自动备份文件失败 {backup.filename}: {e}")
                    continue
            
            # 从数据库删除记录
            db.session.delete(backup)
            deleted_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'已清理 {deleted_count} 个旧自动备份，保留最近 {keep_count} 个',
            'deleted': deleted_count
        })
    except Exception as e:
        db.session.rollback()
        print(f"清理自动备份错误: {e}")
        return jsonify({'success': False, 'error': f'清理失败: {str(e)}'}), 500


def cleanup_old_auto_backups():
    """辅助函数：清理旧的自动备份，只保留最近5个"""
    try:
        # 获取所有自动备份，按时间倒序
        auto_backups = BackupFile.query.filter_by(backup_type='auto').order_by(BackupFile.created_at.desc()).all()
        
        # 只保留最近5个
        keep_count = 5
        if len(auto_backups) <= keep_count:
            return 0
        
        # 删除旧的自动备份
        deleted_count = 0
        for backup in auto_backups[keep_count:]:
            # 删除文件
            abs_path = backup.get_absolute_path()
            if os.path.exists(abs_path):
                try:
                    os.remove(abs_path)
                except Exception as e:
                    print(f"删除自动备份文件失败 {backup.filename}: {e}")
                    continue
            
            # 从数据库删除记录
            db.session.delete(backup)
            deleted_count += 1
        
        db.session.commit()
        return deleted_count
    except Exception as e:
        db.session.rollback()
        print(f"清理自动备份错误: {e}")
        return 0


# ==================== 数据库备份管理 ====================

@admin_bp.route('/api/admin/dbbackup/create', methods=['POST'])
@login_required
@admin_required
def api_create_db_backup():
    """创建数据库备份"""
    try:
        from config import config
        
        # 获取当前数据库路径
        app = current_app
        db_path = app.config.get('SQLITE_PATH', os.path.join(BASE_DIR, 'data', 'wzry.db'))
        
        if not os.path.exists(db_path):
            return jsonify({'success': False, 'error': '数据库文件不存在'}), 404
        
        # 创建备份目录
        backup_dir = os.path.join(BASE_DIR, 'backup')
        os.makedirs(backup_dir, exist_ok=True)
        
        # 生成备份文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'wzry_db_backup_{timestamp}.db'
        filepath = os.path.join(backup_dir, filename)
        
        # 复制数据库文件
        import shutil
        shutil.copy2(db_path, filepath)
        
        # 记录到数据库（使用相对路径）
        relative_path = os.path.join('backup', filename)
        backup_record = BackupFile(
            filename=filename,
            filepath=relative_path,
            file_size=os.path.getsize(filepath),
            backup_type='manual',
            file_type='database',
            description='数据库完整备份'
        )
        db.session.add(backup_record)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': '数据库备份创建成功',
            'filename': filename,
            'backup': backup_record.to_dict()
        })
    except Exception as e:
        print(f"创建数据库备份错误: {e}")
        return jsonify({'success': False, 'error': f'创建备份失败: {str(e)}'}), 500


@admin_bp.route('/api/admin/dbbackup/<int:backup_id>/download', methods=['GET'])
@login_required
@admin_required
def api_download_db_backup(backup_id):
    """下载数据库备份"""
    backup = BackupFile.query.get_or_404(backup_id)
    abs_path = backup.get_absolute_path()
    
    if backup.file_type != 'database':
        return jsonify({'success': False, 'error': '不是数据库备份文件'}), 400
    
    if not os.path.exists(abs_path):
        return jsonify({'success': False, 'error': '备份文件不存在'}), 404
    
    return send_file(
        abs_path,
        as_attachment=True,
        download_name=backup.filename,
        mimetype='application/x-sqlite3'
    )


@admin_bp.route('/api/admin/dbbackup/import', methods=['POST'])
@login_required
@admin_required
def api_import_db_backup():
    """导入数据库备份（上传到备份目录，不恢复）"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '没有上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '没有选择文件'}), 400
        
        # 检查文件扩展名
        if not file.filename.endswith('.db'):
            return jsonify({'success': False, 'error': '只支持 .db 格式的数据库文件'}), 400
        
        # 创建备份目录
        backup_dir = os.path.join(BASE_DIR, 'backup')
        os.makedirs(backup_dir, exist_ok=True)
        
        # 保存文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"imported_{timestamp}_{file.filename}"
        filepath = os.path.join(backup_dir, filename)
        file.save(filepath)
        
        # 验证是否是有效的SQLite数据库
        try:
            import sqlite3
            conn = sqlite3.connect(filepath)
            cursor = conn.cursor()
            # 检查是否有users表（基本验证）
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cursor.fetchone():
                conn.close()
                os.remove(filepath)
                return jsonify({'success': False, 'error': '无效的数据库文件：缺少必要的表结构'}), 400
            conn.close()
        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'success': False, 'error': f'无效的数据库文件: {str(e)}'}), 400
        
        # 记录到数据库（使用相对路径）
        relative_path = os.path.join('backup', filename)
        backup_record = BackupFile(
            filename=filename,
            filepath=relative_path,
            file_size=os.path.getsize(filepath),
            backup_type='imported',
            file_type='database',
            description='导入的数据库备份'
        )
        db.session.add(backup_record)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '数据库备份导入成功',
            'filename': filename,
            'backup': backup_record.to_dict()
        })
    except Exception as e:
        print(f"导入数据库备份错误: {e}")
        return jsonify({'success': False, 'error': f'导入失败: {str(e)}'}), 500


@admin_bp.route('/api/admin/dbbackup/<int:backup_id>/restore', methods=['POST'])
@login_required
@admin_required
def api_restore_db_backup(backup_id):
    """恢复数据库备份（会覆盖当前数据库）"""
    try:
        backup = BackupFile.query.get_or_404(backup_id)
        abs_path = backup.get_absolute_path()
        
        if backup.file_type != 'database':
            return jsonify({'success': False, 'error': '不是数据库备份文件'}), 400
        
        if not os.path.exists(abs_path):
            return jsonify({'success': False, 'error': '备份文件不存在'}), 404
        
        # 获取当前数据库路径
        app = current_app
        db_path = app.config.get('SQLITE_PATH', os.path.join(BASE_DIR, 'data', 'wzry.db'))
        
        # 先备份当前数据库（以防万一）
        backup_dir = os.path.join(BASE_DIR, 'backup')
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        auto_backup_filename = f'auto_backup_before_restore_{timestamp}.db'
        auto_backup_path = os.path.join(backup_dir, auto_backup_filename)
        
        import shutil
        if os.path.exists(db_path):
            shutil.copy2(db_path, auto_backup_path)
            
            # 记录自动备份（使用相对路径）
            auto_backup_relative = os.path.join('backup', auto_backup_filename)
            auto_backup_record = BackupFile(
                filename=auto_backup_filename,
                filepath=auto_backup_relative,
                file_size=os.path.getsize(auto_backup_path),
                backup_type='auto',
                file_type='database',
                description='恢复前自动备份'
            )
            db.session.add(auto_backup_record)
            
            # 清理旧的自动备份（只保留最近5个）
            cleanup_old_auto_backups()
        
        # 复制备份文件到数据库位置
        shutil.copy2(abs_path, db_path)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '数据库恢复成功，请重新登录系统',
            'auto_backup': auto_backup_filename if os.path.exists(auto_backup_path) else None,
            'need_rescan': True
        })
    except Exception as e:
        print(f"恢复数据库备份错误: {e}")
        return jsonify({'success': False, 'error': f'恢复失败: {str(e)}'}), 500
