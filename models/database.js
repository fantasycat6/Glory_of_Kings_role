/**
 * 数据存储模块 - 使用SQLite数据库
 * 英雄数据从JSON文件初始化，存储在数据库中
 */

const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const fs = require('fs');
const bcrypt = require('bcryptjs');

const DB_PATH = path.join(__dirname, '..', 'data', 'database.db');
const HEROES_JSON_PATH = path.join(__dirname, '..', 'data', 'heroes_official.json');
const HERO_IMAGES_JSON_PATH = path.join(__dirname, '..', 'data', 'hero_images.json');

let db = null;

// 从JSON文件加载英雄数据（只读，不修改源文件）
function loadHeroesFromJson() {
  try {
    const data = fs.readFileSync(HEROES_JSON_PATH, 'utf8');
    return JSON.parse(data);
  } catch (err) {
    console.error('加载英雄数据失败:', err);
    return { heroes: [], defaultHeroNames: [] };
  }
}

// 从JSON文件加载英雄图片数据
function loadHeroImagesFromJson() {
  try {
    const data = fs.readFileSync(HERO_IMAGES_JSON_PATH, 'utf8');
    return JSON.parse(data);
  } catch (err) {
    console.error('加载英雄图片数据失败:', err);
    return {};
  }
}

// 生成唯一ID
function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

// 初始化数据库
function initDatabase() {
  return new Promise((resolve, reject) => {
    db = new sqlite3.Database(DB_PATH, (err) => {
      if (err) {
        console.error('数据库连接失败:', err);
        reject(err);
        return;
      }
      console.log('已连接到SQLite数据库');
      
      db.run('PRAGMA foreign_keys = ON', (err) => {
        if (err) {
          console.error('启用外键约束失败:', err);
          reject(err);
          return;
        }
        createTables().then(() => initDefaultData()).then(resolve).catch(reject);
      });
    });
  });
}

// 创建表结构
function createTables() {
  return new Promise((resolve, reject) => {
    const schema = `
      CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT,
        isAdmin INTEGER DEFAULT 0,
        createdAt TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS accounts (
        id TEXT PRIMARY KEY,
        userId TEXT NOT NULL,
        name TEXT NOT NULL,
        loginType TEXT,
        platform TEXT DEFAULT 'android',
        createdAt TEXT NOT NULL,
        FOREIGN KEY (userId) REFERENCES users(id) ON DELETE CASCADE
      );

      CREATE TABLE IF NOT EXISTS regions (
        id TEXT PRIMARY KEY,
        accountId TEXT NOT NULL,
        name TEXT NOT NULL,
        createdAt TEXT NOT NULL,
        FOREIGN KEY (accountId) REFERENCES accounts(id) ON DELETE CASCADE
      );

      CREATE TABLE IF NOT EXISTS hero_ownership (
        id TEXT PRIMARY KEY,
        accountId TEXT NOT NULL,
        regionId TEXT NOT NULL,
        heroName TEXT NOT NULL,
        obtainedAt TEXT NOT NULL,
        FOREIGN KEY (accountId) REFERENCES accounts(id) ON DELETE CASCADE,
        UNIQUE(accountId, regionId, heroName)
      );

      CREATE TABLE IF NOT EXISTS heroes (
        name TEXT PRIMARY KEY,
        role TEXT NOT NULL,
        isDefault INTEGER DEFAULT 0
      );

      CREATE TABLE IF NOT EXISTS backup_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        filepath TEXT,
        file_size INTEGER,
        backup_type TEXT DEFAULT 'manual',
        description TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
      );

      CREATE INDEX IF NOT EXISTS idx_accounts_userId ON accounts(userId);
      CREATE INDEX IF NOT EXISTS idx_regions_accountId ON regions(accountId);
      CREATE INDEX IF NOT EXISTS idx_hero_ownership_accountId ON hero_ownership(accountId);
      CREATE INDEX IF NOT EXISTS idx_hero_ownership_regionId ON hero_ownership(regionId);
    `;

    db.exec(schema, (err) => {
      if (err) {
        console.error('创建表失败:', err);
        reject(err);
        return;
      }
      resolve();
    });
  });
}

// 初始化默认数据（从JSON加载英雄数据）
async function initDefaultData() {
  const { heroes, defaultHeroNames } = loadHeroesFromJson();
  
  // 检查是否已有英雄数据
  const count = await new Promise((resolve, reject) => {
    db.get('SELECT COUNT(*) as count FROM heroes', (err, row) => {
      if (err) reject(err);
      else resolve(row.count);
    });
  });
  
  if (count === 0 && heroes.length > 0) {
    console.log(`初始化 ${heroes.length} 位英雄数据...`);
    const stmt = db.prepare('INSERT OR IGNORE INTO heroes (name, role, isDefault) VALUES (?, ?, ?)');
    
    for (const hero of heroes) {
      const isDefault = defaultHeroNames.includes(hero.name) ? 1 : 0;
      stmt.run(hero.name, hero.role, isDefault);
    }
    
    stmt.finalize();
    console.log('英雄数据初始化完成');
  }
  
  // 创建默认管理员账号
  const adminExists = await UserModel.findByUsername('admin');
  if (!adminExists) {
    await UserModel.create({
      username: 'admin',
      password: 'admin123',
      email: 'admin@example.com',
      isAdmin: true
    });
    console.log('默认管理员账号已创建: admin / admin123');
  }
}

// 重置英雄数据（从JSON重新加载）
async function resetHeroData() {
  const { heroes, defaultHeroNames } = loadHeroesFromJson();
  
  return new Promise((resolve, reject) => {
    db.serialize(() => {
      // 清空现有英雄数据
      db.run('DELETE FROM heroes', (err) => {
        if (err) {
          reject(err);
          return;
        }
        
        // 重新插入英雄数据
        const stmt = db.prepare('INSERT INTO heroes (name, role, isDefault) VALUES (?, ?, ?)');
        
        for (const hero of heroes) {
          const isDefault = defaultHeroNames.includes(hero.name) ? 1 : 0;
          stmt.run(hero.name, hero.role, isDefault);
        }
        
        stmt.finalize((err) => {
          if (err) reject(err);
          else {
            console.log(`英雄数据已重置: ${heroes.length} 位英雄`);
            resolve({ heroes: heroes.length, defaultHeroes: defaultHeroNames.length });
          }
        });
      });
    });
  });
}

// ==================== 用户相关操作 ====================

const UserModel = {
  create(userData) {
    return new Promise((resolve, reject) => {
      const hashedPassword = bcrypt.hashSync(userData.password, 10);
      const id = generateId();
      const createdAt = new Date().toISOString();
      
      const sql = `INSERT INTO users (id, username, password, email, isAdmin, createdAt) 
                   VALUES (?, ?, ?, ?, ?, ?)`;
      
      db.run(sql, [id, userData.username, hashedPassword, userData.email || null, userData.isAdmin ? 1 : 0, createdAt], function(err) {
        if (err) {
          reject(err);
          return;
        }
        resolve({ id, username: userData.username, email: userData.email, isAdmin: userData.isAdmin, createdAt });
      });
    });
  },

  findByUsername(username) {
    return new Promise((resolve, reject) => {
      db.get('SELECT * FROM users WHERE username = ?', [username], (err, row) => {
        if (err) reject(err);
        else resolve(row || null);
      });
    });
  },

  findById(id) {
    return new Promise((resolve, reject) => {
      db.get('SELECT id, username, email, isAdmin, createdAt FROM users WHERE id = ?', [id], (err, row) => {
        if (err) reject(err);
        else resolve(row || null);
      });
    });
  },

  async verifyPassword(username, password) {
    const user = await this.findByUsername(username);
    if (!user) return null;
    const isValid = bcrypt.compareSync(password, user.password);
    if (isValid) {
      const { password, ...userWithoutPassword } = user;
      return userWithoutPassword;
    }
    return null;
  },

  findAll() {
    return new Promise((resolve, reject) => {
      db.all('SELECT id, username, email, isAdmin, createdAt FROM users', [], (err, rows) => {
        if (err) reject(err);
        else resolve(rows);
      });
    });
  },

  update(id, updates) {
    return new Promise(async (resolve, reject) => {
      const fields = [];
      const values = [];
      
      if (updates.username !== undefined) { fields.push('username = ?'); values.push(updates.username); }
      if (updates.password !== undefined) { fields.push('password = ?'); values.push(bcrypt.hashSync(updates.password, 10)); }
      if (updates.email !== undefined) { fields.push('email = ?'); values.push(updates.email); }
      if (updates.isAdmin !== undefined) { fields.push('isAdmin = ?'); values.push(updates.isAdmin ? 1 : 0); }
      
      if (fields.length === 0) {
        resolve(await this.findById(id));
        return;
      }
      
      values.push(id);
      const sql = `UPDATE users SET ${fields.join(', ')} WHERE id = ?`;
      
      db.run(sql, values, async function(err) {
        if (err) reject(err);
        else resolve(await UserModel.findById(id));
      });
    });
  },

  delete(id) {
    return new Promise((resolve, reject) => {
      db.run('DELETE FROM users WHERE id = ?', [id], function(err) {
        if (err) reject(err);
        else resolve(this.changes > 0);
      });
    });
  }
};

// ==================== 账号相关操作 ====================

const AccountModel = {
  create(accountData) {
    return new Promise((resolve, reject) => {
      const id = generateId();
      const createdAt = new Date().toISOString();
      
      db.run('INSERT INTO accounts (id, userId, name, loginType, platform, createdAt) VALUES (?, ?, ?, ?, ?, ?)',
        [id, accountData.userId, accountData.name, accountData.loginType, accountData.platform || 'android', createdAt],
        async function(err) {
          if (err) {
            reject(err);
            return;
          }
          // 自动为新账号添加默认英雄
          const defaultHeroes = await HeroModel.getDefaultHeroes();
          for (const hero of defaultHeroes) {
            await HeroOwnershipModel.addDefault(id, hero.name);
          }
          resolve({ id, userId: accountData.userId, name: accountData.name, loginType: accountData.loginType, platform: accountData.platform || 'android', createdAt });
        });
    });
  },

  findByUserId(userId) {
    return new Promise((resolve, reject) => {
      db.all('SELECT * FROM accounts WHERE userId = ?', [userId], (err, rows) => {
        if (err) reject(err);
        else resolve(rows);
      });
    });
  },

  findById(id) {
    return new Promise((resolve, reject) => {
      db.get('SELECT * FROM accounts WHERE id = ?', [id], (err, row) => {
        if (err) reject(err);
        else resolve(row || null);
      });
    });
  },

  delete(id) {
    return new Promise((resolve, reject) => {
      db.run('DELETE FROM accounts WHERE id = ?', [id], function(err) {
        if (err) reject(err);
        else resolve(this.changes > 0);
      });
    });
  }
};

// ==================== 区服相关操作 ====================

const RegionModel = {
  async create(regionData) {
    const id = generateId();
    const createdAt = new Date().toISOString();
    
    return new Promise((resolve, reject) => {
      db.run('INSERT INTO regions (id, accountId, name, createdAt) VALUES (?, ?, ?, ?)',
        [id, regionData.accountId, regionData.name, createdAt],
        async function(err) {
          if (err) {
            reject(err);
            return;
          }
          
          const region = { id, accountId: regionData.accountId, name: regionData.name, createdAt };
          
          // 自动为新角色添加默认英雄
          const defaultHeroes = await HeroModel.getDefaultHeroes();
          for (const hero of defaultHeroes) {
            await HeroOwnershipModel.add(regionData.accountId, id, hero.name);
          }
          
          resolve(region);
        });
    });
  },

  findByAccountId(accountId) {
    return new Promise((resolve, reject) => {
      db.all('SELECT * FROM regions WHERE accountId = ?', [accountId], (err, rows) => {
        if (err) reject(err);
        else resolve(rows);
      });
    });
  },

  findById(id) {
    return new Promise((resolve, reject) => {
      db.get('SELECT * FROM regions WHERE id = ?', [id], (err, row) => {
        if (err) reject(err);
        else resolve(row || null);
      });
    });
  },

  delete(id) {
    return new Promise((resolve, reject) => {
      db.run('DELETE FROM regions WHERE id = ?', [id], function(err) {
        if (err) reject(err);
        else resolve(this.changes > 0);
      });
    });
  }
};

// ==================== 英雄拥有相关操作 ====================

const HeroOwnershipModel = {
  add(accountId, regionId, heroName) {
    return new Promise((resolve, reject) => {
      const id = generateId();
      const obtainedAt = new Date().toISOString();
      
      db.run('INSERT OR IGNORE INTO hero_ownership (id, accountId, regionId, heroName, obtainedAt) VALUES (?, ?, ?, ?, ?)',
        [id, accountId, regionId, heroName, obtainedAt],
        function(err) {
          if (err) reject(err);
          else resolve({ id, accountId, regionId, heroName, obtainedAt });
        });
    });
  },

  // 为账号添加默认英雄（不指定regionId）
  addDefault(accountId, heroName) {
    return new Promise((resolve, reject) => {
      const id = generateId();
      const obtainedAt = new Date().toISOString();
      
      // 使用accountId作为regionId的占位符
      db.run('INSERT OR IGNORE INTO hero_ownership (id, accountId, regionId, heroName, obtainedAt) VALUES (?, ?, ?, ?, ?)',
        [id, accountId, 'default', heroName, obtainedAt],
        function(err) {
          if (err) reject(err);
          else resolve({ id, accountId, regionId: 'default', heroName, obtainedAt });
        });
    });
  },

  remove(accountId, regionId, heroName) {
    return new Promise((resolve, reject) => {
      db.run('DELETE FROM hero_ownership WHERE accountId = ? AND regionId = ? AND heroName = ?',
        [accountId, regionId, heroName],
        function(err) {
          if (err) reject(err);
          else resolve(this.changes > 0);
        });
    });
  },

  getOwnedHeroes(accountId, regionId) {
    return new Promise((resolve, reject) => {
      db.all('SELECT heroName FROM hero_ownership WHERE accountId = ? AND regionId = ?',
        [accountId, regionId],
        (err, rows) => {
          if (err) reject(err);
          else resolve(rows.map(r => r.heroName));
        });
    });
  },

  // 获取所有用户的英雄拥有记录（用于备份恢复）
  getAllOwnerships() {
    return new Promise((resolve, reject) => {
      db.all('SELECT accountId, regionId, heroName, obtainedAt FROM hero_ownership', [],
        (err, rows) => {
          if (err) reject(err);
          else resolve(rows);
        });
    });
  },

  // 批量恢复英雄拥有记录（用于备份恢复）
  restoreOwnerships(ownerships) {
    return new Promise((resolve, reject) => {
      if (!ownerships || ownerships.length === 0) {
        resolve(0);
        return;
      }
      
      const stmt = db.prepare('INSERT OR IGNORE INTO hero_ownership (id, accountId, regionId, heroName, obtainedAt) VALUES (?, ?, ?, ?, ?)');
      let count = 0;
      
      for (const item of ownerships) {
        const id = generateId();
        stmt.run([id, item.accountId, item.regionId, item.heroName, item.obtainedAt || new Date().toISOString()], (err) => {
          if (!err) count++;
        });
      }
      
      stmt.finalize((err) => {
        if (err) reject(err);
        else resolve(count);
      });
    });
  },

  hasHero(accountId, regionId, heroName) {
    return new Promise((resolve, reject) => {
      db.get('SELECT COUNT(*) as count FROM hero_ownership WHERE accountId = ? AND regionId = ? AND heroName = ?',
        [accountId, regionId, heroName],
        (err, row) => {
          if (err) reject(err);
          else resolve(row.count > 0);
        });
    });
  },

  async getStats(accountId, regionId) {
    const ownedHeroNames = await this.getOwnedHeroes(accountId, regionId);
    const allHeroes = await HeroModel.findAll();
    const totalHeroes = allHeroes.length;
    
    const byRole = {};
    allHeroes.forEach(hero => {
      const roles = hero.role.split('/');
      roles.forEach(role => {
        if (!byRole[role]) byRole[role] = { total: 0, owned: 0 };
        byRole[role].total++;
        if (ownedHeroNames.includes(hero.name)) byRole[role].owned++;
      });
    });
    
    return {
      total: totalHeroes,
      owned: ownedHeroNames.length,
      percentage: totalHeroes > 0 ? Math.round((ownedHeroNames.length / totalHeroes) * 100) : 0,
      byRole
    };
  },

  batchUpdate(accountId, regionId, heroNames, owned) {
    return new Promise(async (resolve, reject) => {
      if (owned) {
        const stmt = db.prepare('INSERT OR IGNORE INTO hero_ownership (id, accountId, regionId, heroName, obtainedAt) VALUES (?, ?, ?, ?, ?)');
        const obtainedAt = new Date().toISOString();
        
        for (const heroName of heroNames) {
          const id = generateId();
          stmt.run([id, accountId, regionId, heroName, obtainedAt]);
        }
        
        stmt.finalize((err) => {
          if (err) reject(err);
          else resolve();
        });
      } else {
        const placeholders = heroNames.map(() => '?').join(',');
        db.run(`DELETE FROM hero_ownership WHERE accountId = ? AND regionId = ? AND heroName IN (${placeholders})`,
          [accountId, regionId, ...heroNames],
          function(err) {
            if (err) reject(err);
            else resolve();
          });
      }
    });
  }
};

// ==================== 英雄数据操作（从数据库读取） ====================

const HeroModel = {
  findAll() {
    return new Promise((resolve, reject) => {
      db.all('SELECT * FROM heroes ORDER BY name', (err, rows) => {
        if (err) reject(err);
        else resolve(rows || []);
      });
    });
  },

  findByName(name) {
    return new Promise((resolve, reject) => {
      db.get('SELECT * FROM heroes WHERE name = ?', [name], (err, row) => {
        if (err) reject(err);
        else resolve(row || null);
      });
    });
  },

  findByRole(role) {
    return new Promise((resolve, reject) => {
      db.all('SELECT * FROM heroes WHERE role LIKE ?', [`%${role}%`], (err, rows) => {
        if (err) reject(err);
        else resolve(rows || []);
      });
    });
  },

  async getAllRoles() {
    const heroes = await this.findAll();
    const roleSet = new Set();
    heroes.forEach(hero => {
      hero.role.split('/').forEach(role => roleSet.add(role));
    });
    return Array.from(roleSet).sort();
  },

  async getDefaultHeroes() {
    return new Promise((resolve, reject) => {
      db.all('SELECT * FROM heroes WHERE isDefault = 1 ORDER BY name', (err, rows) => {
        if (err) reject(err);
        else resolve(rows || []);
      });
    });
  },

  async getDefaultHeroNames() {
    const heroes = await this.getDefaultHeroes();
    return heroes.map(h => h.name);
  },

  async getSortedByName() {
    const heroes = await this.findAll();
    return heroes.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'));
  },

  async search(query) {
    const heroes = await this.findAll();
    const lowerQuery = query.toLowerCase();
    return heroes.filter(h => 
      h.name.toLowerCase().includes(lowerQuery) ||
      h.role.toLowerCase().includes(lowerQuery)
    );
  },

  add(heroData) {
    return new Promise(async (resolve, reject) => {
      const existing = await this.findByName(heroData.name);
      if (existing) {
        reject(new Error('英雄已存在'));
        return;
      }

      db.run('INSERT INTO heroes (name, role, isDefault) VALUES (?, ?, ?)',
        [heroData.name, heroData.role, heroData.isDefault ? 1 : 0],
        function(err) {
          if (err) reject(err);
          else resolve({ name: heroData.name, role: heroData.role, isDefault: heroData.isDefault || false });
        });
    });
  },

  update(name, updates) {
    return new Promise(async (resolve, reject) => {
      const existing = await this.findByName(name);
      if (!existing) {
        reject(new Error('英雄不存在'));
        return;
      }

      if (updates.name && updates.name !== name) {
        const newNameExists = await this.findByName(updates.name);
        if (newNameExists) {
          reject(new Error('新名称的英雄已存在'));
          return;
        }
      }

      const fields = [];
      const values = [];
      
      if (updates.name !== undefined) { fields.push('name = ?'); values.push(updates.name); }
      if (updates.role !== undefined) { fields.push('role = ?'); values.push(updates.role); }
      if (updates.isDefault !== undefined) { fields.push('isDefault = ?'); values.push(updates.isDefault ? 1 : 0); }
      
      if (fields.length === 0) {
        resolve(existing);
        return;
      }

      // 如果名称改变，需要更新外键引用
      if (updates.name && updates.name !== name) {
        db.run('UPDATE hero_ownership SET heroName = ? WHERE heroName = ?', [updates.name, name], (err) => {
          if (err) {
            console.error('更新英雄拥有记录失败:', err);
          }
        });
      }
      
      values.push(name);
      db.run(`UPDATE heroes SET ${fields.join(', ')} WHERE name = ?`, values, async function(err) {
        if (err) reject(err);
        else {
          const newName = updates.name || name;
          resolve(await HeroModel.findByName(newName));
        }
      });
    });
  },

  delete(name) {
    return new Promise(async (resolve, reject) => {
      const existing = await this.findByName(name);
      if (!existing) {
        reject(new Error('英雄不存在'));
        return;
      }

      // 先删除相关的拥有记录
      db.run('DELETE FROM hero_ownership WHERE heroName = ?', [name], (err) => {
        if (err) console.error('删除英雄拥有记录失败:', err);
        
        db.run('DELETE FROM heroes WHERE name = ?', [name], function(err) {
          if (err) reject(err);
          else resolve(true);
        });
      });
    });
  },

  setDefaultHero(name, isDefault) {
    return this.update(name, { isDefault });
  },

  // 从JSON文件重新加载（重置功能）
  async resetFromJson() {
    return resetHeroData();
  }
};

// ==================== 备份文件相关操作 ====================

const BackupFileModel = {
  create(filename, filepath, fileSize, backupType = 'manual', description = '') {
    return new Promise((resolve, reject) => {
      db.run('INSERT INTO backup_files (filename, filepath, file_size, backup_type, description, created_at) VALUES (?, ?, ?, ?, ?, datetime("now", "localtime"))',
        [filename, filepath, fileSize, backupType, description],
        function(err) {
          if (err) reject(err);
          else resolve({
            id: this.lastID,
            filename,
            filepath,
            file_size: fileSize,
            backup_type: backupType,
            description,
            created_at: new Date().toISOString()
          });
        });
    });
  },

  findAll() {
    return new Promise((resolve, reject) => {
      db.all('SELECT * FROM backup_files ORDER BY created_at DESC', (err, rows) => {
        if (err) reject(err);
        else resolve(rows || []);
      });
    });
  },

  findById(id) {
    return new Promise((resolve, reject) => {
      db.get('SELECT * FROM backup_files WHERE id = ?', [id], (err, row) => {
        if (err) reject(err);
        else resolve(row);
      });
    });
  },

  delete(id) {
    return new Promise((resolve, reject) => {
      db.run('DELETE FROM backup_files WHERE id = ?', [id], function(err) {
        if (err) reject(err);
        else resolve();
      });
    });
  },

  deleteByFilename(filename) {
    return new Promise((resolve, reject) => {
      db.run('DELETE FROM backup_files WHERE filename = ?', [filename], function(err) {
        if (err) reject(err);
        else resolve();
      });
    });
  }
};

// ==================== 英雄图片数据 ====================

const HeroImageModel = {
  getAll() {
    return loadHeroImagesFromJson();
  },

  getByName(name) {
    const images = loadHeroImagesFromJson();
    return images[name] || null;
  }
};

// 获取数据库实例
function getDb() {
  return db;
}

// 关闭数据库连接
function closeDatabase() {
  return new Promise((resolve, reject) => {
    if (db) {
      db.close((err) => {
        if (err) {
          reject(err);
          return;
        }
        console.log('数据库连接已关闭');
        resolve();
      });
    } else {
      resolve();
    }
  });
}

module.exports = {
  initDatabase,
  closeDatabase,
  getDb,
  User: UserModel,
  Account: AccountModel,
  Region: RegionModel,
  HeroOwnership: HeroOwnershipModel,
  Hero: HeroModel,
  BackupFile: BackupFileModel,
  HeroImage: HeroImageModel
};
