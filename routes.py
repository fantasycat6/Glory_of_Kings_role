"""
主路由蓝图 - 首页、账号管理、区服管理、英雄管理、个人中心
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_login import login_required, current_user
from models import db, User, Account, Region, Hero, HeroOwnership, get_hero_images

main_bp = Blueprint('main', __name__)


# ==================== 公开路由 ====================

@main_bp.route('/')
def index():
    """首页"""
    return render_template('index.html')


# ==================== 账号管理 ====================

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """我的账号页面"""
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', accounts=accounts)


@main_bp.route('/accounts/add', methods=['GET', 'POST'])
@login_required
def add_account():
    """添加账号"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        login_type = request.form.get('loginType', 'qq')
        platform = request.form.get('platform', 'android')
        
        if not name:
            flash('账号名称不能为空', 'error')
            return render_template('account_add.html')
        
        account = Account(
            user_id=current_user.id,
            name=name,
            login_type=login_type,
            platform=platform
        )
        db.session.add(account)
        db.session.commit()
        
        flash('账号添加成功', 'success')
        return redirect(url_for('main.dashboard'))
    
    return render_template('account_add.html')


@main_bp.route('/accounts/<int:account_id>/delete', methods=['POST'])
@login_required
def delete_account(account_id):
    """删除账号"""
    account = Account.query.get_or_404(account_id)
    
    if account.user_id != current_user.id:
        abort(403)
    
    db.session.delete(account)
    db.session.commit()
    
    flash('账号已删除', 'success')
    return redirect(url_for('main.dashboard'))


# ==================== 区服管理 ====================

@main_bp.route('/accounts/<int:account_id>')
@login_required
def account_detail(account_id):
    """账号详情（区服列表）"""
    account = Account.query.get_or_404(account_id)
    
    if account.user_id != current_user.id:
        abort(403)
    
    regions = Region.query.filter_by(account_id=account_id).all()
    return render_template('account_detail.html', account=account, regions=regions)


@main_bp.route('/accounts/<int:account_id>/regions/add', methods=['POST'])
@login_required
def add_region(account_id):
    """添加区服"""
    account = Account.query.get_or_404(account_id)
    
    if account.user_id != current_user.id:
        abort(403)
    
    region_name = request.form.get('regionName', '').strip()
    
    if not region_name:
        if request.is_json:
            return jsonify({'error': '区服名称不能为空'}), 400
        flash('区服名称不能为空', 'error')
        return redirect(url_for('main.account_detail', account_id=account_id))
    
    region = Region(account_id=account_id, name=region_name)
    db.session.add(region)
    
    # 自动添加默认英雄
    default_heroes = Hero.get_default_heroes()
    for hero in default_heroes:
        ownership = HeroOwnership(
            account_id=account_id,
            region_id=region.id,
            hero_name=hero.name
        )
        db.session.add(ownership)
    
    db.session.commit()
    
    if request.is_json:
        return jsonify({'success': True, 'region': region.to_dict()})
    
    flash('区服添加成功', 'success')
    return redirect(url_for('main.account_detail', account_id=account_id))


@main_bp.route('/regions/<int:region_id>/delete', methods=['POST'])
@login_required
def delete_region(region_id):
    """删除区服"""
    region = Region.query.get_or_404(region_id)
    account = Account.query.get(region.account_id)
    
    if account.user_id != current_user.id:
        abort(403)
    
    db.session.delete(region)
    db.session.commit()
    
    flash('区服已删除', 'success')
    return redirect(url_for('main.account_detail', account_id=account.id))


# ==================== 英雄管理 ====================

@main_bp.route('/regions/<int:region_id>/heroes')
@login_required
def heroes(region_id):
    """英雄管理页面"""
    region = Region.query.get_or_404(region_id)
    account = Account.query.get(region.account_id)
    
    if account.user_id != current_user.id:
        abort(403)
    
    heroes = Hero.get_sorted_by_name()
    owned_hero_names = HeroOwnership.get_owned_heroes(account.id, region.id)
    stats = HeroOwnership.get_stats(account.id, region.id)
    hero_images = get_hero_images()
    
    return render_template('heroes.html',
                         region=region,
                         account=account,
                         heroes=heroes,
                         owned_hero_names=owned_hero_names,
                         stats=stats,
                         hero_images=hero_images)


@main_bp.route('/regions/<int:region_id>/heroes/update', methods=['POST'])
@login_required
def update_hero(region_id):
    """更新单个英雄状态"""
    region = Region.query.get_or_404(region_id)
    account = Account.query.get(region.account_id)
    
    if account.user_id != current_user.id:
        return jsonify({'error': '无权操作'}), 403
    
    hero_name = request.form.get('heroName')
    owned = request.form.get('owned') == 'true'
    
    if owned:
        # 添加拥有记录
        existing = HeroOwnership.query.filter_by(
            account_id=account.id,
            region_id=region.id,
            hero_name=hero_name
        ).first()
        if not existing:
            ownership = HeroOwnership(
                account_id=account.id,
                region_id=region.id,
                hero_name=hero_name
            )
            db.session.add(ownership)
    else:
        # 移除拥有记录
        HeroOwnership.query.filter_by(
            account_id=account.id,
            region_id=region.id,
            hero_name=hero_name
        ).delete()
    
    db.session.commit()
    
    stats = HeroOwnership.get_stats(account.id, region.id)
    return jsonify({'success': True, 'stats': stats})


@main_bp.route('/regions/<int:region_id>/heroes/batch-update', methods=['POST'])
@login_required
def batch_update_heroes(region_id):
    """批量更新英雄状态"""
    region = Region.query.get_or_404(region_id)
    account = Account.query.get(region.account_id)
    
    if account.user_id != current_user.id:
        return jsonify({'error': '无权操作'}), 403
    
    data = request.get_json()
    hero_names = data.get('heroNames', [])
    owned = data.get('owned', False)
    
    HeroOwnership.batch_update(account.id, region.id, hero_names, owned)
    
    stats = HeroOwnership.get_stats(account.id, region.id)
    return jsonify({'success': True, 'stats': stats})


@main_bp.route('/regions/<int:region_id>/stats')
@login_required
def get_region_stats(region_id):
    """获取区服统计信息"""
    region = Region.query.get_or_404(region_id)
    account = Account.query.get(region.account_id)
    
    if account.user_id != current_user.id:
        return jsonify({'error': '无权访问'}), 403
    
    stats = HeroOwnership.get_stats(account.id, region.id)
    return jsonify(stats)


# ==================== 英雄搜索API ====================

@main_bp.route('/api/heroes/search')
@login_required
def search_heroes():
    """搜索英雄API"""
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify([])
    
    results = Hero.search(query)
    return jsonify([hero.to_dict() for hero in results])


# ==================== 个人中心 ====================

@main_bp.route('/profile')
@login_required
def profile():
    """个人中心"""
    return render_template('profile.html')


@main_bp.route('/api/user/profile', methods=['PUT'])
@login_required
def update_profile():
    """更新个人资料"""
    data = request.get_json()
    email = data.get('email', '').strip()
    
    current_user.email = email
    db.session.commit()
    
    return jsonify({'success': True, 'user': current_user.to_dict()})


@main_bp.route('/api/user/password', methods=['PUT'])
@login_required
def change_password():
    """修改密码"""
    data = request.get_json()
    current_password = data.get('currentPassword', '')
    new_password = data.get('newPassword', '')
    
    if not current_password or not new_password:
        return jsonify({'error': '当前密码和新密码不能为空'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': '新密码长度至少6位'}), 400
    
    if not current_user.check_password(current_password):
        return jsonify({'error': '当前密码错误'}), 400
    
    current_user.set_password(new_password)
    db.session.commit()
    
    return jsonify({'success': True})


# ==================== 错误处理 ====================

@main_bp.route('/favicon.ico')
def favicon():
    """处理favicon请求"""
    return redirect('/static/favicon.ico')
