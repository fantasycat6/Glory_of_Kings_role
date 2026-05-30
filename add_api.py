#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
添加数据库迁移API到admin.py
"""

def add_migration_api():
    with open('admin.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 检查是否已经添加
    content = ''.join(lines)
    if 'api_validate_migration' in content:
        print('API already installed')
        return
    
    # 新的API代码
    new_code = '''

# ==================== 数据库迁移 ====================

@admin_bp.route('/api/admin/migration/validate', methods=['POST'])
@login_required
@admin_required
def api_validate_migration():
    """验证旧数据库文件"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '没有上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '没有选择文件'}), 400
        
        # 检查文件扩展名
        if not file.filename.endswith('.db'):
            return jsonify({'success': False, 'error': '只支持 .db 格式的数据库文件'}), 400
        
        # 保存到临时目录
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        
        try:
            # 导入迁移器并验证
            from database_migration import DatabaseMigration
            migration = DatabaseMigration(tmp_path)
            validation = migration.validate_old_database()
            
            return jsonify({
                'success': True,
                'validation': validation
            })
        finally:
            # 删除临时文件
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
    except Exception as e:
        print(f"验证数据库文件错误: {e}")
        return jsonify({'success': False, 'error': f'验证失败: {str(e)}'}), 500


@admin_bp.route('/api/admin/migration/preview', methods=['POST'])
@login_required
@admin_required
def api_preview_migration():
    """预览迁移数据"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '没有上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '没有选择文件'}), 400
        
        # 检查文件扩展名
        if not file.filename.endswith('.db'):
            return jsonify({'success': False, 'error': '只支持 .db 格式的数据库文件'}), 400
        
        # 保存到临时目录
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        
        try:
            # 导入迁移器并验证
            from database_migration import DatabaseMigration
            migration = DatabaseMigration(tmp_path)
            validation = migration.validate_old_database()
            
            if not validation['valid']:
                return jsonify({
                    'success': False,
                    'error': validation['message']
                }), 400
            
            # 获取预览数据
            preview_data = {
                'users': [],
                'accounts': [],
                'regions': [],
                'hero_ownerships': 0,
                'skins': 0,
                'skin_ownerships': 0
            }
            
            # 读取旧数据库
            import sqlite3
            conn = sqlite3.connect(tmp_path)
            cursor = conn.cursor()
            
            # 获取用户预览
            cursor.execute("SELECT username FROM users LIMIT 10")
            preview_data['users'] = [row[0] for row in cursor.fetchall()]
            
            # 获取账号预览
            cursor.execute("SELECT name FROM accounts LIMIT 10")
            preview_data['accounts'] = [row[0] for row in cursor.fetchall()]
            
            # 获取区服预览
            cursor.execute("SELECT name FROM regions LIMIT 10")
            preview_data['regions'] = [row[0] for row in cursor.fetchall()]
            
            # 获取统计
            cursor.execute("SELECT COUNT(*) FROM hero_ownership")
            preview_data['hero_ownerships'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM skins")
            preview_data['skins'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM skin_ownership")
            preview_data['skin_ownerships'] = cursor.fetchone()[0]
            
            conn.close()
            
            return jsonify({
                'success': True,
                'validation': validation,
                'preview': preview_data
            })
        finally:
            # 删除临时文件
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
    except Exception as e:
        print(f"预览迁移数据错误: {e}")
        return jsonify({'success': False, 'error': f'预览失败: {str(e)}'}), 500


@admin_bp.route('/api/admin/migration/execute', methods=['POST'])
@login_required
@admin_required
def api_execute_migration():
    """执行数据库迁移"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '没有上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '没有选择文件'}), 400
        
        # 检查文件扩展名
        if not file.filename.endswith('.db'):
            return jsonify({'success': False, 'error': '只支持 .db 格式的数据库文件'}), 400
        
        # 获取迁移模式
        mode = request.form.get('mode', 'merge')  # merge 或 replace
        
        # 保存到临时目录
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        
        try:
            # 导入迁移器
            from database_migration import DatabaseMigration
            migration = DatabaseMigration(tmp_path)
            
            # 先验证
            validation = migration.validate_old_database()
            if not validation['valid']:
                return jsonify({
                    'success': False,
                    'error': validation['message']
                }), 400
            
            # 执行迁移
            app = current_app._get_current_object()
            result = migration.migrate_data(app, mode)
            
            return jsonify(result)
        finally:
            # 删除临时文件
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
    except Exception as e:
        print(f"执行数据库迁移错误: {e}")
        return jsonify({'success': False, 'error': f'迁移失败: {str(e)}'}), 500

'''
    
    # 添加新代码
    lines.append(new_code)
    
    # 写回文件
    with open('admin.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print('Migration API added successfully!')

if __name__ == '__main__':
    add_migration_api()
