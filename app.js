/**
 * 王者荣耀英雄统计网站 - 主应用文件
 * 技术栈: Node.js + Express + SQLite + EJS + JWT + Cookie
 */

const express = require('express');
const path = require('path');
const fs = require('fs');
const multer = require('multer');
const jwt = require('jsonwebtoken');
require('dotenv').config();

const { initDatabase, closeDatabase, Hero, HeroImage } = require('./models/database');

const app = express();
const PORT = process.env.PORT || 3000;

// JWT 密钥
const JWT_SECRET = process.env.JWT_SECRET || 'wzry-jwt-secret-key-change-in-production';

// ==================== 配置 ====================

// 基础中间件
const cookieParser = require('cookie-parser');
app.use(cookieParser());
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// 模板引擎
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// 全局变量中间件
app.use((req, res, next) => {
  // 从 cookie 或 Authorization 头获取 token
  const token = req.cookies?.token || req.headers.authorization?.replace('Bearer ', '');
  if (token) {
    try {
      req.user = jwt.verify(token, JWT_SECRET);
    } catch (e) {
      req.user = null;
    }
  } else {
    req.user = null;
  }
  res.locals.user = req.user;
  res.locals.path = req.path;
  next();
});

// 生成 JWT Token
function generateToken(user) {
  return jwt.sign(
    { 
      id: user.id, 
      username: user.username, 
      isAdmin: user.isAdmin 
    },
    JWT_SECRET,
    { expiresIn: '7d' }
  );
}

// ==================== 中间件 ====================

// 检查是否为API请求（简单判断：以/api/开头的都是API）
const isApiRequest = (req) => {
  return req.path.startsWith('/api/');
};

const requireAuth = (req, res, next) => {
  if (!req.user) {
    if (isApiRequest(req)) {
      return res.status(401).json({ error: '请先登录' });
    }
    return res.redirect('/login');
  }
  next();
};

const requireAdmin = (req, res, next) => {
  if (!req.user?.isAdmin) {
    if (isApiRequest(req)) {
      return res.status(403).json({ error: '需要管理员权限' });
    }
    return res.status(403).render('error', { 
      message: '需要管理员权限',
      user: req.user,
      path: req.path
    });
  }
  next();
};

// ==================== 工具函数 ====================

const formatFileSize = (bytes) => {
  if (!bytes || bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes, unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  return size.toFixed(1) + ' ' + units[unitIndex];
};

const formatDateTime = (dateStr) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  });
};

// ==================== 公开路由 ====================

app.get('/', (req, res) => {
  res.render('index', { title: '王者荣耀英雄统计', user: req.user });
});

// 登录
app.get('/login', (req, res) => {
  if (req.user) return res.redirect('/dashboard');
  res.render('login', { title: '登录', error: null });
});

app.post('/login', async (req, res) => {
  const { username, password } = req.body;
  const { User } = require('./models/database');
  
  try {
    const user = await User.verifyPassword(username, password);
    if (user) {
      // 生成 JWT token
      const token = generateToken(user);
      // 设置 cookie
      res.cookie('token', token, { 
        httpOnly: true, 
        maxAge: 7 * 24 * 60 * 60 * 1000,
        sameSite: 'lax'
      });
      res.redirect('/dashboard');
    } else {
      res.render('login', { title: '登录', error: '用户名或密码错误' });
    }
  } catch (err) {
    console.error('登录错误:', err);
    res.render('login', { title: '登录', error: '服务器错误' });
  }
});

// 注册
app.get('/register', (req, res) => {
  if (req.user) return res.redirect('/dashboard');
  res.render('register', { title: '注册', error: null });
});

app.post('/register', async (req, res) => {
  const { username, password, confirmPassword, email } = req.body;
  const { User } = require('./models/database');
  
  if (password !== confirmPassword) {
    return res.render('register', { title: '注册', error: '两次输入的密码不一致' });
  }
  
  if (password.length < 6) {
    return res.render('register', { title: '注册', error: '密码长度至少6位' });
  }
  
  try {
    const existingUser = await User.findByUsername(username);
    if (existingUser) {
      return res.render('register', { title: '注册', error: '用户名已存在' });
    }
    
    await User.create({ username, password, email });
    res.redirect('/login');
  } catch (err) {
    console.error('注册错误:', err);
    res.render('register', { title: '注册', error: '注册失败，请重试' });
  }
});

// 退出登录
app.get('/logout', (req, res) => {
  res.clearCookie('token');
  res.redirect('/');
});

// ==================== 用户路由 ====================

app.get('/dashboard', requireAuth, async (req, res) => {
  const { Account } = require('./models/database');
  try {
    const accounts = await Account.findByUserId(req.user.id);
    res.render('dashboard', { title: '我的账号', accounts });
  } catch (err) {
    console.error('获取账号列表错误:', err);
    res.status(500).render('error', { message: '获取账号列表失败', user: req.user, path: req.path });
  }
});

// 账号管理
app.get('/accounts/add', requireAuth, (req, res) => {
  res.render('account-add', { title: '添加账号', error: null });
});

app.post('/accounts/add', requireAuth, async (req, res) => {
  const { name, loginType, platform } = req.body;
  const { Account } = require('./models/database');
  
  try {
    await Account.create({ userId: req.user.id, name, loginType, platform: platform || 'android' });
    res.redirect('/dashboard');
  } catch (err) {
    console.error('添加账号错误:', err);
    res.status(500).render('error', { message: '添加账号失败', user: req.user, path: req.path });
  }
});

app.post('/accounts/:id/delete', requireAuth, async (req, res) => {
  const { Account } = require('./models/database');
  try {
    const account = await Account.findById(req.params.id);
    if (!account || account.userId !== req.user.id) {
      return res.status(403).send('无权操作');
    }
    await Account.delete(req.params.id);
    res.redirect('/dashboard');
  } catch (err) {
    console.error('删除账号错误:', err);
    res.status(500).send('删除失败');
  }
});

// 区服管理
app.get('/accounts/:id', requireAuth, async (req, res) => {
  const { Account, Region } = require('./models/database');
  try {
    const account = await Account.findById(req.params.id);
    if (!account || account.userId !== req.user.id) {
      return res.status(403).render('error', { message: '无权访问此账号', user: req.user, path: req.path });
    }
    const regions = await Region.findByAccountId(req.params.id);
    res.render('account-detail', { title: account.name, account, regions });
  } catch (err) {
    console.error('获取账号详情错误:', err);
    res.status(500).render('error', { message: '获取账号详情失败', user: req.user, path: req.path });
  }
});

app.post('/accounts/:id/regions/add', requireAuth, async (req, res) => {
  const { regionName } = req.body;
  const { Account, Region } = require('./models/database');
  try {
    const account = await Account.findById(req.params.id);
    if (!account || account.userId !== req.user.id) {
      return res.status(403).send('无权操作');
    }
    if (!regionName?.trim()) {
      return res.status(400).send('区服名称不能为空');
    }
    await Region.create({ accountId: req.params.id, name: regionName.trim() });
    res.redirect(`/accounts/${req.params.id}`);
  } catch (err) {
    console.error('添加区服错误:', err);
    res.status(500).send('添加区服失败');
  }
});

app.post('/regions/:id/delete', requireAuth, async (req, res) => {
  const { Region, Account } = require('./models/database');
  try {
    const region = await Region.findById(req.params.id);
    if (!region) return res.status(404).send('区服不存在');
    const account = await Account.findById(region.accountId);
    if (!account || account.userId !== req.user.id) {
      return res.status(403).send('无权操作');
    }
    await Region.delete(req.params.id);
    res.redirect(`/accounts/${region.accountId}`);
  } catch (err) {
    console.error('删除区服错误:', err);
    res.status(500).send('删除区服失败');
  }
});

// 英雄管理页面
app.get('/regions/:id/heroes', requireAuth, async (req, res) => {
  const { Region, Account, HeroOwnership } = require('./models/database');
  try {
    const region = await Region.findById(req.params.id);
    if (!region) return res.status(404).render('error', { message: '区服不存在', user: req.user, path: req.path });
    
    const account = await Account.findById(region.accountId);
    if (!account || account.userId !== req.user.id) {
      return res.status(403).render('error', { message: '无权访问此区服', user: req.user, path: req.path });
    }
    
    const heroes = await Hero.getSortedByName();
    const ownedHeroNames = await HeroOwnership.getOwnedHeroes(region.accountId, region.id);
    const stats = await HeroOwnership.getStats(region.accountId, region.id);
    const heroImages = HeroImage.getAll();
    
    res.render('heroes', { 
      title: `${region.name} - 英雄管理`,
      region, account, heroes, ownedHeroNames, stats, heroImages
    });
  } catch (err) {
    console.error('获取英雄页面错误:', err);
    res.status(500).render('error', { message: '获取英雄页面失败', user: req.user, path: req.path });
  }
});

// 英雄状态更新
app.post('/regions/:id/heroes/update', requireAuth, async (req, res) => {
  const { heroName, owned } = req.body;
  const { Region, Account, HeroOwnership } = require('./models/database');
  try {
    const region = await Region.findById(req.params.id);
    if (!region) return res.status(404).json({ error: '区服不存在' });
    
    const account = await Account.findById(region.accountId);
    if (!account || account.userId !== req.user.id) {
      return res.status(403).json({ error: '无权操作' });
    }
    
    if (owned === 'true' || owned === true) {
      await HeroOwnership.add(region.accountId, region.id, heroName);
    } else {
      await HeroOwnership.remove(region.accountId, region.id, heroName);
    }
    
    const stats = await HeroOwnership.getStats(region.accountId, region.id);
    res.json({ success: true, stats });
  } catch (err) {
    console.error('更新英雄状态错误:', err);
    res.status(500).json({ error: '更新失败' });
  }
});

app.post('/regions/:id/heroes/batch-update', requireAuth, async (req, res) => {
  const { heroNames, owned } = req.body;
  const { Region, Account, HeroOwnership } = require('./models/database');
  try {
    const region = await Region.findById(req.params.id);
    if (!region) return res.status(404).json({ error: '区服不存在' });
    
    const account = await Account.findById(region.accountId);
    if (!account || account.userId !== req.user.id) {
      return res.status(403).json({ error: '无权操作' });
    }
    
    if (!Array.isArray(heroNames)) {
      return res.status(400).json({ error: '英雄列表格式错误' });
    }
    
    await HeroOwnership.batchUpdate(region.accountId, region.id, heroNames, owned === true);
    const stats = await HeroOwnership.getStats(region.accountId, region.id);
    res.json({ success: true, stats });
  } catch (err) {
    console.error('批量更新错误:', err);
    res.status(500).json({ error: '批量更新失败' });
  }
});

app.get('/regions/:id/stats', requireAuth, async (req, res) => {
  const { Region, Account, HeroOwnership } = require('./models/database');
  try {
    const region = await Region.findById(req.params.id);
    if (!region) return res.status(404).json({ error: '区服不存在' });
    
    const account = await Account.findById(region.accountId);
    if (!account || account.userId !== req.user.id) {
      return res.status(403).json({ error: '无权访问' });
    }
    
    const stats = await HeroOwnership.getStats(region.accountId, region.id);
    res.json(stats);
  } catch (err) {
    console.error('获取统计信息错误:', err);
    res.status(500).json({ error: '获取统计信息失败' });
  }
});

// 搜索英雄
app.get('/api/heroes/search', requireAuth, async (req, res) => {
  const { q } = req.query;
  if (!q?.trim()) return res.json([]);
  try {
    const results = await Hero.search(q.trim());
    res.json(results);
  } catch (err) {
    console.error('搜索英雄错误:', err);
    res.status(500).json({ error: '搜索失败' });
  }
});

// ==================== 用户中心 ====================

app.get('/profile', requireAuth, (req, res) => {
  res.render('profile', { title: '个人中心', user: req.user });
});

app.put('/api/user/profile', requireAuth, async (req, res) => {
  const { email } = req.body;
  const { User } = require('./models/database');
  try {
    const updatedUser = await User.update(req.user.id, { email });
    if (updatedUser) {
      // 重新生成 token
      const token = generateToken(updatedUser);
      res.cookie('token', token, { 
        httpOnly: true, 
        maxAge: 7 * 24 * 60 * 60 * 1000,
        sameSite: 'lax'
      });
      res.json({ success: true, user: updatedUser });
    } else {
      res.status(400).json({ error: '更新失败' });
    }
  } catch (err) {
    console.error('更新资料错误:', err);
    res.status(500).json({ error: '更新失败' });
  }
});

app.put('/api/user/password', requireAuth, async (req, res) => {
  const { currentPassword, newPassword } = req.body;
  const { User } = require('./models/database');
  
  if (!currentPassword || !newPassword) {
    return res.status(400).json({ error: '当前密码和新密码不能为空' });
  }
  if (newPassword.length < 6) {
    return res.status(400).json({ error: '新密码长度至少6位' });
  }
  
  try {
    const user = await User.verifyPassword(req.user.username, currentPassword);
    if (!user) return res.status(400).json({ error: '当前密码错误' });
    
    await User.update(req.user.id, { password: newPassword });
    res.json({ success: true });
  } catch (err) {
    console.error('修改密码错误:', err);
    res.status(500).json({ error: '修改密码失败' });
  }
});

// ==================== 管理员路由 ====================

// 管理后台首页
app.get('/admin', requireAuth, requireAdmin, async (req, res) => {
  const { User } = require('./models/database');
  try {
    const users = await User.findAll();
    const heroes = await Hero.findAll();
    res.render('admin/dashboard', { title: '管理员后台', users, heroes });
  } catch (err) {
    console.error('管理员首页错误:', err);
    res.status(500).render('error', { message: '加载管理页面失败', user: req.user, path: req.path });
  }
});

// 用户管理页面
app.get('/admin/users', requireAuth, requireAdmin, async (req, res) => {
  const { User } = require('./models/database');
  try {
    const users = await User.findAll();
    res.render('admin/users', { title: '用户管理', users, currentUser: req.user });
  } catch (err) {
    console.error('用户管理页面错误:', err);
    res.status(500).render('error', { message: '加载用户管理页面失败', user: req.user, path: req.path });
  }
});

// 英雄管理页面
app.get('/admin/heroes', requireAuth, requireAdmin, (req, res) => {
  res.render('admin/heroes', { title: '英雄管理' });
});

// 备份管理页面
app.get('/admin/backup', requireAuth, requireAdmin, (req, res) => {
  res.render('admin/backup', { title: '数据备份管理' });
});

// ==================== 管理员API ====================

// 用户管理API
app.get('/api/admin/users', requireAuth, requireAdmin, async (req, res) => {
  const { User } = require('./models/database');
  try {
    const users = await User.findAll();
    res.json(users);
  } catch (err) {
    console.error('获取用户列表错误:', err);
    res.status(500).json({ error: '获取用户列表失败' });
  }
});

app.get('/api/admin/users/:id', requireAuth, requireAdmin, async (req, res) => {
  const { User } = require('./models/database');
  try {
    const user = await User.findById(req.params.id);
    if (!user) return res.status(404).json({ error: '用户不存在' });
    res.json(user);
  } catch (err) {
    console.error('获取用户信息错误:', err);
    res.status(500).json({ error: '获取用户信息失败' });
  }
});

app.post('/api/admin/users', requireAuth, requireAdmin, async (req, res) => {
  const { username, password, email, isAdmin } = req.body;
  const { User } = require('./models/database');
  
  if (!username || !password) return res.status(400).json({ error: '用户名和密码不能为空' });
  if (password.length < 6) return res.status(400).json({ error: '密码长度至少6位' });
  
  try {
    const existingUser = await User.findByUsername(username);
    if (existingUser) return res.status(400).json({ error: '用户名已存在' });
    
    const user = await User.create({ username, password, email, isAdmin: isAdmin === 'true' || isAdmin === true });
    res.json({ success: true, user });
  } catch (err) {
    console.error('创建用户错误:', err);
    res.status(500).json({ error: '创建用户失败' });
  }
});

app.put('/api/admin/users/:id', requireAuth, requireAdmin, async (req, res) => {
  const { username, email, isAdmin, password } = req.body;
  const { User } = require('./models/database');
  
  try {
    const user = await User.findById(req.params.id);
    if (!user) return res.status(404).json({ error: '用户不存在' });
    
    if (user.isAdmin && !isAdmin) {
      const allUsers = await User.findAll();
      const adminCount = allUsers.filter(u => u.isAdmin).length;
      if (adminCount <= 1) return res.status(400).json({ error: '至少需要保留一个管理员' });
    }
    
    const updates = { username, email };
    if (isAdmin !== undefined) updates.isAdmin = isAdmin === 'true' || isAdmin === true;
    if (password && password.length >= 6) updates.password = password;
    
    const updatedUser = await User.update(req.params.id, updates);
    res.json({ success: true, user: updatedUser });
  } catch (err) {
    console.error('更新用户错误:', err);
    res.status(500).json({ error: '更新用户失败' });
  }
});

app.delete('/api/admin/users/:id', requireAuth, requireAdmin, async (req, res) => {
  const { User } = require('./models/database');
  try {
    const user = await User.findById(req.params.id);
    if (!user) return res.status(404).json({ error: '用户不存在' });
    if (user.id === req.user.id) return res.status(400).json({ error: '不能删除当前登录的账号' });
    
    if (user.isAdmin) {
      const allUsers = await User.findAll();
      const adminCount = allUsers.filter(u => u.isAdmin).length;
      if (adminCount <= 1) return res.status(400).json({ error: '至少需要保留一个管理员' });
    }
    
    await User.delete(req.params.id);
    res.json({ success: true });
  } catch (err) {
    console.error('删除用户错误:', err);
    res.status(500).json({ error: '删除用户失败' });
  }
});

// 英雄管理API
app.get('/api/admin/heroes', requireAuth, requireAdmin, async (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const roleFilter = req.query.role || 'all';
  const searchQuery = req.query.search || '';
  const isDefaultFilter = req.query.isDefault || 'all';
  const perPage = 10;
  
  try {
    let heroes = await Hero.getSortedByName();
    const defaultHeroNames = (await Hero.getDefaultHeroes()).map(h => h.name);
    
    // 筛选
    if (roleFilter !== 'all') {
      heroes = heroes.filter(h => h.role.includes(roleFilter));
    }
    if (searchQuery) {
      const lowerQuery = searchQuery.toLowerCase();
      heroes = heroes.filter(h => h.name.toLowerCase().includes(lowerQuery));
    }
    if (isDefaultFilter !== 'all') {
      const isDefault = isDefaultFilter === 'true';
      heroes = heroes.filter(h => defaultHeroNames.includes(h.name) === isDefault);
    }
    
    // 分页
    const totalHeroes = heroes.length;
    const totalPages = Math.ceil(totalHeroes / perPage);
    const currentPage = Math.max(1, Math.min(page, totalPages || 1));
    const startIndex = (currentPage - 1) * perPage;
    const endIndex = startIndex + perPage;
    const paginatedHeroes = heroes.slice(startIndex, endIndex);
    
    const roles = await Hero.getAllRoles();
    const heroImages = HeroImage.getAll();
    
    res.json({
      success: true,
      heroes: paginatedHeroes,
      allHeroes: await Hero.findAll(),
      defaultHeroNames,
      heroImages,
      roles,
      pagination: {
        currentPage,
        totalPages,
        totalHeroes,
        perPage,
        startIndex: startIndex + 1,
        endIndex: Math.min(endIndex, totalHeroes)
      },
      filters: { role: roleFilter, search: searchQuery }
    });
  } catch (err) {
    console.error('获取英雄列表错误:', err);
    res.status(500).json({ error: '获取英雄列表失败' });
  }
});

app.post('/api/admin/heroes', requireAuth, requireAdmin, async (req, res) => {
  const { name, role, isDefault } = req.body;
  if (!name || !role) return res.status(400).json({ error: '英雄名称和职业不能为空' });
  
  try {
    const hero = await Hero.add({ name, role, isDefault: isDefault === true || isDefault === 'true' });
    res.json({ success: true, hero });
  } catch (err) {
    console.error('添加英雄错误:', err);
    res.status(500).json({ error: '添加英雄失败: ' + err.message });
  }
});

app.put('/api/admin/heroes/:name', requireAuth, requireAdmin, async (req, res) => {
  const { name: newName, role, isDefault } = req.body;
  const oldName = decodeURIComponent(req.params.name);
  
  try {
    const hero = await Hero.update(oldName, { name: newName, role, isDefault: isDefault === true || isDefault === 'true' });
    res.json({ success: true, hero });
  } catch (err) {
    console.error('更新英雄错误:', err);
    res.status(500).json({ error: '更新英雄失败: ' + err.message });
  }
});

app.delete('/api/admin/heroes/:name', requireAuth, requireAdmin, async (req, res) => {
  const heroName = decodeURIComponent(req.params.name);
  try {
    await Hero.delete(heroName);
    res.json({ success: true });
  } catch (err) {
    console.error('删除英雄错误:', err);
    res.status(500).json({ error: '删除英雄失败' });
  }
});

// 重置英雄数据（从JSON重新加载）
app.post('/api/admin/heroes/reset', requireAuth, requireAdmin, async (req, res) => {
  try {
    const result = await Hero.resetFromJson();
    res.json({ success: true, message: `英雄数据已重置: ${result.heroes} 位英雄`, result });
  } catch (err) {
    console.error('重置英雄数据错误:', err);
    res.status(500).json({ error: '重置英雄数据失败: ' + err.message });
  }
});

// ==================== 备份管理 ====================

// 确保备份目录存在
const backupDir = path.join(__dirname, 'backup');
if (!fs.existsSync(backupDir)) {
  fs.mkdirSync(backupDir, { recursive: true });
}

// 配置multer存储
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, backupDir),
  filename: (req, file, cb) => {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    cb(null, `import_${timestamp}_${file.originalname}`);
  }
});

const upload = multer({ 
  storage,
  limits: { fileSize: 10 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    if (file.mimetype === 'application/json' || file.originalname.endsWith('.json')) {
      cb(null, true);
    } else {
      cb(new Error('只接受JSON文件'));
    }
  }
});

// 导出备份
app.get('/api/admin/backup/export', requireAuth, requireAdmin, async (req, res) => {
  try {
    const heroes = await Hero.findAll();
    const defaultHeroes = await Hero.getDefaultHeroes();
    
    const backupData = {
      version: '1.0',
      exported_at: new Date().toISOString(),
      heroes,
      default_heroes: defaultHeroes.map(h => h.name)
    };
    
    const filename = `wzry_backup_${new Date().toISOString().slice(0,10).replace(/-/g,'')}_${Date.now()}.json`;
    
    res.setHeader('Content-Type', 'application/json');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.send(JSON.stringify(backupData, null, 2));
  } catch (err) {
    console.error('导出备份错误:', err);
    res.status(500).json({ error: '导出备份失败' });
  }
});

// 创建备份
app.post('/api/admin/backup/create', requireAuth, requireAdmin, async (req, res) => {
  const { BackupFile } = require('./models/database');
  try {
    const heroes = await Hero.findAll();
    const defaultHeroes = await Hero.getDefaultHeroes();
    
    const backupData = {
      version: '1.0',
      exported_at: new Date().toISOString(),
      heroes,
      default_heroes: defaultHeroes.map(h => h.name)
    };
    
    const filename = `wzry_backup_${new Date().toISOString().slice(0,10).replace(/-/g,'')}_${Date.now()}.json`;
    const filepath = path.join(backupDir, filename);
    
    fs.writeFileSync(filepath, JSON.stringify(backupData, null, 2));
    
    await BackupFile.create(filename, filepath, fs.statSync(filepath).size, 'manual', '');
    res.json({ success: true, filename });
  } catch (err) {
    console.error('创建备份错误:', err);
    res.status(500).json({ error: '创建备份失败' });
  }
});

// 导入备份
app.post('/api/admin/backup/import', requireAuth, requireAdmin, async (req, res) => {
  const { data, mode } = req.body;
  if (!data?.heroes || !Array.isArray(data.heroes)) {
    return res.status(400).json({ error: '无效的备份文件格式' });
  }
  
  try {
    const { HeroOwnership } = require('./models/database');
    let imported = 0, skipped = 0, errors = 0;
    let ownershipBackup = [];
    
    // 覆盖模式：先备份用户拥有记录，然后清空现有英雄
    if (mode === 'overwrite') {
      ownershipBackup = await HeroOwnership.getAllOwnerships();
      console.log(`备份了 ${ownershipBackup.length} 条用户拥有记录`);
      
      const currentHeroes = await Hero.findAll();
      for (const hero of currentHeroes) {
        try { await Hero.delete(hero.name); } catch (e) { console.error('删除英雄错误:', e); }
      }
    }
    
    // 导入英雄
    for (const heroData of data.heroes) {
      try {
        if (!heroData.name || !heroData.role) { errors++; continue; }
        
        const existing = await Hero.findByName(heroData.name);
        if (existing) {
          if (mode !== 'overwrite') { skipped++; continue; }
        }
        
        const isDefault = data.default_heroes?.includes(heroData.name);
        await Hero.add({ name: heroData.name, role: heroData.role });
        if (isDefault) await Hero.setDefaultHero(heroData.name, true);
        imported++;
      } catch (err) {
        console.error('导入英雄错误:', heroData.name, err);
        errors++;
      }
    }
    
    // 恢复用户拥有记录（过滤掉已删除的英雄）
    let restoredOwnerships = 0;
    if (mode === 'overwrite' && ownershipBackup.length > 0) {
      const newHeroNames = new Set((await Hero.findAll()).map(h => h.name));
      const validOwnerships = ownershipBackup.filter(o => newHeroNames.has(o.heroName));
      restoredOwnerships = await HeroOwnership.restoreOwnerships(validOwnerships);
      console.log(`恢复了 ${restoredOwnerships} 条用户拥有记录`);
    }
    
    res.json({ 
      success: true, 
      message: `导入完成：成功 ${imported} 个英雄，跳过 ${skipped} 个，失败 ${errors} 个${restoredOwnerships > 0 ? `，恢复 ${restoredOwnerships} 条用户记录` : ''}`,
      imported, skipped, errors, restoredOwnerships
    });
  } catch (err) {
    console.error('导入备份错误:', err);
    res.status(500).json({ error: '导入备份失败: ' + err.message });
  }
});

// 获取备份列表
app.get('/api/admin/backup/list', requireAuth, requireAdmin, async (req, res) => {
  const { BackupFile } = require('./models/database');
  try {
    const backups = await BackupFile.findAll();
    const formattedBackups = backups.map(backup => ({
      ...backup,
      file_size_formatted: formatFileSize(backup.file_size),
      created_at_formatted: formatDateTime(backup.created_at)
    }));
    res.json({ success: true, backups: formattedBackups });
  } catch (err) {
    console.error('获取备份列表错误:', err);
    res.status(500).json({ error: '获取备份列表失败' });
  }
});

// 下载备份
app.get('/api/admin/backup/download/:id', requireAuth, requireAdmin, async (req, res) => {
  const { BackupFile } = require('./models/database');
  try {
    let backup = await BackupFile.findById(req.params.id);
    let filename = backup ? backup.filename : req.params.id;
    let filepath = path.join(backupDir, filename);
    
    if (!filepath.startsWith(backupDir)) return res.status(403).send('非法路径');
    if (!fs.existsSync(filepath)) return res.status(404).send('文件不存在');
    
    res.download(filepath, filename);
  } catch (err) {
    console.error('下载备份错误:', err);
    res.status(500).json({ error: '下载失败' });
  }
});

// 恢复备份
app.post('/api/admin/backup/restore/:id', requireAuth, requireAdmin, async (req, res) => {
  const { mode } = req.body;
  const { BackupFile, HeroOwnership } = require('./models/database');
  
  try {
    let backup = await BackupFile.findById(req.params.id);
    let filename = backup ? backup.filename : req.params.id;
    let filepath = path.join(backupDir, filename);
    
    if (!filepath.startsWith(backupDir)) return res.status(403).json({ error: '非法路径' });
    if (!fs.existsSync(filepath)) return res.status(404).json({ error: '备份文件不存在' });
    
    const content = fs.readFileSync(filepath, 'utf8');
    const data = JSON.parse(content);
    
    if (!data?.heroes || !Array.isArray(data.heroes)) {
      return res.status(400).json({ error: '无效的备份文件格式' });
    }
    
    let imported = 0, skipped = 0, errors = 0;
    let ownershipBackup = [];
    
    // 覆盖模式：先备份用户拥有记录，然后清空现有英雄
    if (mode === 'overwrite') {
      ownershipBackup = await HeroOwnership.getAllOwnerships();
      console.log(`备份了 ${ownershipBackup.length} 条用户拥有记录`);
      
      const currentHeroes = await Hero.findAll();
      for (const hero of currentHeroes) {
        try { await Hero.delete(hero.name); } catch (e) { console.error('删除英雄错误:', e); }
      }
    }
    
    // 恢复英雄
    for (const heroData of data.heroes) {
      try {
        if (!heroData.name || !heroData.role) { errors++; continue; }
        
        const existing = await Hero.findByName(heroData.name);
        if (existing && mode !== 'overwrite') { skipped++; continue; }
        
        const isDefault = data.default_heroes?.includes(heroData.name);
        await Hero.add({ name: heroData.name, role: heroData.role });
        if (isDefault) await Hero.setDefaultHero(heroData.name, true);
        imported++;
      } catch (err) {
        console.error('恢复英雄错误:', heroData.name, err);
        errors++;
      }
    }
    
    // 恢复用户拥有记录（过滤掉已删除的英雄）
    let restoredOwnerships = 0;
    if (mode === 'overwrite' && ownershipBackup.length > 0) {
      const newHeroNames = new Set((await Hero.findAll()).map(h => h.name));
      const validOwnerships = ownershipBackup.filter(o => newHeroNames.has(o.heroName));
      restoredOwnerships = await HeroOwnership.restoreOwnerships(validOwnerships);
      console.log(`恢复了 ${restoredOwnerships} 条用户拥有记录`);
    }
    
    res.json({ 
      success: true, 
      message: `恢复完成：成功 ${imported} 个英雄，跳过 ${skipped} 个，失败 ${errors} 个${restoredOwnerships > 0 ? `，恢复 ${restoredOwnerships} 条用户记录` : ''}`,
      imported, skipped, errors, restoredOwnerships
    });
  } catch (err) {
    console.error('恢复备份错误:', err);
    res.status(500).json({ error: '恢复备份失败: ' + err.message });
  }
});

// 删除备份
app.delete('/api/admin/backup/:id', requireAuth, requireAdmin, async (req, res) => {
  const { BackupFile } = require('./models/database');
  try {
    let backup = await BackupFile.findById(req.params.id);
    let filename = backup ? backup.filename : req.params.id;
    let filepath = path.join(backupDir, filename);
    
    if (!filepath.startsWith(backupDir)) {
      return res.status(403).json({ error: '非法路径' });
    }
    
    if (fs.existsSync(filepath)) {
      fs.unlinkSync(filepath);
    }
    
    if (backup) {
      await BackupFile.delete(backup.id);
    } else {
      await BackupFile.deleteByFilename(filename);
    }
    
    res.json({ success: true });
  } catch (err) {
    console.error('删除备份错误:', err);
    res.status(500).json({ error: '删除备份失败: ' + err.message });
  }
});

// ==================== 错误处理 ====================

app.use((req, res) => {
  res.status(404).render('error', { 
    message: '页面未找到',
    user: req.user,
    path: req.path
  });
});

app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).render('error', { 
    message: '服务器内部错误',
    user: req.user,
    path: req.path
  });
});

// ==================== 启动 ====================

async function startServer() {
  try {
    await initDatabase();
    console.log('数据库初始化完成');
    
    app.listen(PORT, () => {
      console.log(`=================================`);
      console.log(`王者荣耀英雄统计网站已启动`);
      console.log(`访问地址: http://localhost:${PORT}`);
      console.log(`默认管理员: admin / admin123`);
      console.log(`=================================`);
    });
  } catch (err) {
    console.error('启动失败:', err);
    process.exit(1);
  }
}

process.on('SIGINT', async () => {
  console.log('\n正在关闭服务器...');
  await closeDatabase();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('\n正在关闭服务器...');
  await closeDatabase();
  process.exit(0);
});

if (require.main === module) {
  startServer();
}

module.exports = app;
