"""
主路由蓝图 - 首页、账号管理、区服管理、英雄管理、个人中心
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_login import login_required, current_user
from models import db, User, Account, Region, Hero, HeroOwnership, Skin, SkinOwnership, get_hero_images
from pypinyin import lazy_pinyin

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
    accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.sort_order).all()
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
    
    # 先删除关联的皮肤拥有记录
    SkinOwnership.query.filter_by(account_id=account.id).delete()
    
    db.session.delete(account)
    db.session.commit()
    
    flash('账号已删除', 'success')
    return redirect(url_for('main.dashboard'))


@main_bp.route('/api/accounts/<int:account_id>', methods=['PUT'])
@login_required
def update_account(account_id):
    """编辑账号"""
    account = Account.query.get_or_404(account_id)
    
    if account.user_id != current_user.id:
        return jsonify({'error': '无权操作'}), 403
    
    data = request.get_json()
    account.name = data.get('name', account.name).strip()
    account.login_type = data.get('loginType', account.login_type)
    account.platform = data.get('platform', account.platform)
    
    db.session.commit()
    
    return jsonify({'success': True, 'account': account.to_dict()})


@main_bp.route('/api/accounts/reorder', methods=['POST'])
@login_required
def reorder_accounts():
    """更新账号排序"""
    data = request.get_json()
    account_ids = data.get('accountIds', [])
    
    for index, account_id in enumerate(account_ids):
        account = Account.query.get(account_id)
        if account and account.user_id == current_user.id:
            account.sort_order = index
    
    db.session.commit()
    return jsonify({'success': True})


# ==================== 区服管理 ====================

@main_bp.route('/accounts/<int:account_id>')
@login_required
def account_detail(account_id):
    """账号详情（区服列表）"""
    account = Account.query.get_or_404(account_id)
    
    if account.user_id != current_user.id:
        abort(403)
    
    regions = Region.query.filter_by(account_id=account_id).order_by(Region.sort_order).all()
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
    
    # 先删除关联的皮肤拥有记录
    SkinOwnership.query.filter_by(region_id=region.id).delete()
    
    db.session.delete(region)
    db.session.commit()
    
    flash('区服已删除', 'success')
    return redirect(url_for('main.account_detail', account_id=account.id))


@main_bp.route('/api/regions/<int:region_id>', methods=['PUT'])
@login_required
def update_region(region_id):
    """编辑区服"""
    region = Region.query.get_or_404(region_id)
    account = Account.query.get(region.account_id)
    
    if account.user_id != current_user.id:
        return jsonify({'error': '无权操作'}), 403
    
    data = request.get_json()
    region.name = data.get('name', region.name).strip()
    
    db.session.commit()
    
    return jsonify({'success': True, 'region': region.to_dict()})


@main_bp.route('/api/accounts/<int:account_id>/regions/reorder', methods=['POST'])
@login_required
def reorder_regions(account_id):
    """更新区服排序"""
    account = Account.query.get_or_404(account_id)
    
    if account.user_id != current_user.id:
        return jsonify({'error': '无权操作'}), 403
    
    data = request.get_json()
    region_ids = data.get('regionIds', [])
    
    for index, region_id in enumerate(region_ids):
        region = Region.query.get(region_id)
        if region and region.account_id == account_id:
            region.sort_order = index
    
    db.session.commit()
    return jsonify({'success': True})


# ==================== 英雄管理 ====================

@main_bp.route('/regions/<int:region_id>/heroes')
@login_required
def heroes(region_id):
    """英雄管理页面"""
    region = Region.query.get_or_404(region_id)
    account = Account.query.get(region.account_id)
    
    if account.user_id != current_user.id:
        abort(403)
    
    # 获取所有英雄和已拥有的英雄
    all_heroes = Hero.query.all()
    owned_hero_names = HeroOwnership.get_owned_heroes(account.id, region.id)
    
    # 按拼音排序，已拥有的排在前面
    def sort_key(hero):
        pinyin = lazy_pinyin(hero.name)
        is_owned = hero.name in owned_hero_names
        # 已拥有的排在前面（0在前，1在后），然后按拼音排序
        return (0 if is_owned else 1, pinyin)
    
    heroes = sorted(all_heroes, key=sort_key)
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


# ==================== 英雄查询功能 ====================

@main_bp.route('/hero-search')
@login_required
def hero_search():
    """英雄查询页面"""
    return render_template('hero_search.html')


@main_bp.route('/api/search/hero')
@login_required
def api_search_hero_ownership():
    """查询英雄拥有情况API
    
    查询当前用户的所有账号和区服中，哪些已拥有指定英雄
    """
    hero_name = request.args.get('hero', '').strip()
    
    if not hero_name:
        return jsonify({'success': False, 'error': '请输入英雄名称'}), 400
    
    # 查找匹配的英雄（支持模糊搜索）
    hero = Hero.query.filter(Hero.name.like(f'%{hero_name}%')).first()
    
    if not hero:
        return jsonify({
            'success': True,
            'heroName': hero_name,
            'results': []
        })
    
    # 查询当前用户的所有账号
    accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.sort_order).all()
    
    results = []
    
    for account in accounts:
        # 查询该账号下拥有此英雄的区服
        account_regions = []
        
        # 获取该账号的所有区服
        regions = Region.query.filter_by(account_id=account.id).order_by(Region.sort_order).all()
        
        for region in regions:
            # 检查是否拥有该英雄
            ownership = HeroOwnership.query.filter_by(
                account_id=account.id,
                region_id=region.id,
                hero_name=hero.name
            ).first()
            
            if ownership:
                account_regions.append({
                    'regionId': region.id,
                    'regionName': region.name
                })
        
        # 如果该账号下有区服拥有此英雄，添加到结果
        if account_regions:
            results.append({
                'accountId': account.id,
                'accountName': account.name,
                'loginType': account.get_login_type_display(),
                'platform': account.get_platform_display(),
                'regions': account_regions
            })
    
    return jsonify({
        'success': True,
        'heroName': hero.name,
        'results': results
    })


@main_bp.route('/api/search/skin')
@login_required
def api_search_skin_ownership():
    """查询皮肤拥有情况API
    
    查询当前用户的所有账号和区服中，哪些已拥有指定皮肤
    支持输入英雄名称（查询该英雄所有皮肤）或皮肤名称
    """
    query = request.args.get('query', '').strip()
    
    if not query:
        return jsonify({'success': False, 'error': '请输入英雄名称或皮肤名称'}), 400
    
    matched_skin = None
    hero_name = None
    
    # 先尝试作为皮肤名称匹配
    skin = Skin.query.filter(Skin.name.like(f'%{query}%')).first()
    if skin:
        matched_skin = skin
        hero_name = skin.hero_name
    
    # 如果没有匹配到皮肤，尝试作为英雄名称匹配
    if not matched_skin:
        hero = Hero.query.filter(Hero.name.like(f'%{query}%')).first()
        if hero:
            # 获取该英雄的第一个皮肤
            skin = Skin.query.filter_by(hero_name=hero.name).first()
            if skin:
                matched_skin = skin
                hero_name = hero.name
    
    if not matched_skin:
        return jsonify({
            'success': True,
            'skinName': query,
            'heroName': None,
            'results': []
        })
    
    # 查询当前用户的所有账号
    accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.sort_order).all()
    
    results = []
    
    for account in accounts:
        account_regions = []
        
        # 获取该账号的所有区服
        regions = Region.query.filter_by(account_id=account.id).order_by(Region.sort_order).all()
        
        for region in regions:
            # 获取该区服已拥有的皮肤
            owned_skin_ids = SkinOwnership.get_owned_skins(account.id, region.id)
            
            # 获取该英雄的所有皮肤
            hero_skins = Skin.query.filter_by(hero_name=matched_skin.hero_name).all()
            
            # 筛选已拥有的皮肤
            owned_skins = []
            for s in hero_skins:
                if s.id in owned_skin_ids:
                    owned_skins.append({
                        'skinId': s.id,
                        'skinName': s.name
                    })
            
            # 如果该区服拥有该英雄的任何皮肤，添加到结果
            if owned_skins:
                account_regions.append({
                    'regionId': region.id,
                    'regionName': region.name,
                    'ownedSkins': owned_skins
                })
        
        # 如果该账号下有区服拥有该英雄的皮肤，添加到结果
        if account_regions:
            results.append({
                'accountId': account.id,
                'accountName': account.name,
                'loginType': account.get_login_type_display(),
                'platform': account.get_platform_display(),
                'regions': account_regions
            })
    
    return jsonify({
        'success': True,
        'skinName': matched_skin.name,
        'heroName': matched_skin.hero_name,
        'results': results
    })


# ==================== 错误处理 ====================

@main_bp.route('/favicon.ico')
def favicon():
    """处理favicon请求"""
    return redirect('/static/favicon.ico')


# ==================== 皮肤管理 ====================

@main_bp.route('/regions/<int:region_id>/skins')
@login_required
def skins(region_id):
    """皮肤管理页面"""
    region = Region.query.get_or_404(region_id)
    account = Account.query.get(region.account_id)
    
    if account.user_id != current_user.id:
        abort(403)
    
    # 获取所有皮肤和已拥有的皮肤
    all_skins = Skin.query.all()
    owned_skin_ids = SkinOwnership.get_owned_skins(account.id, region.id)
    
    # 获取所有英雄数据（用于职业）
    heroes = Hero.query.all()
    hero_roles = {hero.name: hero.role for hero in heroes}
    
    # 按英雄分组
    skins_by_hero = {}
    for skin in all_skins:
        if skin.hero_name not in skins_by_hero:
            skins_by_hero[skin.hero_name] = []
        skins_by_hero[skin.hero_name].append(skin)
    
    # 对每个英雄的皮肤按ID排序
    for hero_name in skins_by_hero:
        skins_by_hero[hero_name].sort(key=lambda s: s.id)
    
    # 按英雄名称拼音排序
    sorted_hero_names = sorted(skins_by_hero.keys(), key=lambda x: lazy_pinyin(x))
    
    skin_stats = SkinOwnership.get_skin_stats(account.id, region.id)
    
    # 职业选项
    all_roles = ['全部', '坦克', '战士', '刺客', '法师', '射手', '辅助']
    
    return render_template('skins.html',
                         region=region,
                         account=account,
                         skins_by_hero=skins_by_hero,
                         sorted_hero_names=sorted_hero_names,
                         owned_skin_ids=owned_skin_ids,
                         skin_stats=skin_stats,
                         hero_roles=hero_roles,
                         all_roles=all_roles)


@main_bp.route('/regions/<int:region_id>/skins/toggle', methods=['POST'])
@login_required
def toggle_skin(region_id):
    """切换皮肤拥有状态"""
    region = Region.query.get_or_404(region_id)
    account = Account.query.get(region.account_id)
    
    if account.user_id != current_user.id:
        return jsonify({'error': '无权操作'}), 403
    
    data = request.get_json()
    skin_id = data.get('skinId')
    owned = data.get('owned', False)
    
    if not skin_id:
        return jsonify({'error': '皮肤ID不能为空'}), 400
    
    SkinOwnership.toggle_skin(account.id, region.id, skin_id, owned)
    
    skin_stats = SkinOwnership.get_skin_stats(account.id, region.id)
    return jsonify({'success': True, 'skinStats': skin_stats})


@main_bp.route('/regions/<int:region_id>/skins/stats')
@login_required
def get_skin_stats(region_id):
    """获取皮肤统计信息"""
    region = Region.query.get_or_404(region_id)
    account = Account.query.get(region.account_id)
    
    if account.user_id != current_user.id:
        return jsonify({'error': '无权访问'}), 403
    
    skin_stats = SkinOwnership.get_skin_stats(account.id, region.id)
    return jsonify(skin_stats)


@main_bp.route('/collection')
@login_required
def collection():
    """收藏室/图鉴页面 - 显示用户所有账号所有区服的英雄和皮肤（去重）"""
    from models import get_user_collection
    from pypinyin import lazy_pinyin
    
    collection_data = get_user_collection(current_user.id)
    
    # 按拼音排序英雄（用于皮肤部分）
    sorted_hero_names = sorted(collection_data['skins_by_hero'].keys(), key=lambda x: lazy_pinyin(x))
    
    return render_template('collection.html',
                         collection=collection_data,
                         sorted_hero_names=sorted_hero_names)
