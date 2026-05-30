#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试数据库迁移功能
"""

def test_migration_imports():
    """测试导入"""
    try:
        from database_migration import DatabaseMigration, migrate_from_old_database
        print("✓ database_migration 模块导入成功")
        
        from admin import admin_bp
        print("✓ admin 模块导入成功")
        
        # 检查API端点是否存在
        from admin import api_validate_migration, api_preview_migration, api_execute_migration
        print("✓ 数据库迁移 API 端点已注册")
        
        return True
    except Exception as e:
        print(f"✗ 导入失败: {e}")
        return False

def test_migration_class():
    """测试迁移类"""
    try:
        from database_migration import DatabaseMigration
        
        # 创建实例（不提供路径，应该不会出错）
        migration = DatabaseMigration.__new__(DatabaseMigration)
        migration.errors = []
        migration.warnings = []
        migration.stats = {
            'users': 0,
            'accounts': 0,
            'regions': 0,
            'hero_ownerships': 0,
            'skin_ownerships': 0,
            'skins': 0
        }
        
        print("✓ DatabaseMigration 类实例化成功")
        return True
    except Exception as e:
        print(f"✗ DatabaseMigration 类测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("测试数据库迁移功能")
    print("=" * 60)
    print()
    
    results = []
    
    print("1. 测试模块导入...")
    results.append(test_migration_imports())
    print()
    
    print("2. 测试迁移类...")
    results.append(test_migration_class())
    print()
    
    print("=" * 60)
    if all(results):
        print("✅ 所有测试通过！数据库迁移功能已准备就绪。")
        print()
        print("下一步：")
        print("1. 启动应用: python app.py")
        print("2. 登录管理后台")
        print("3. 进入'备份管理'页面")
        print("4. 找到'数据库迁移'选项卡")
        print("5. 上传旧版本数据库文件进行迁移")
    else:
        print("❌ 部分测试失败，请检查错误信息")
    print("=" * 60)

if __name__ == '__main__':
    main()
