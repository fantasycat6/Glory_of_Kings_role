# 王者荣耀英雄统计网站

[![Node.js](https://img.shields.io/badge/Node.js-18+-green.svg)](https://nodejs.org/)
[![Express](https://img.shields.io/badge/Express-5.x-blue.svg)](https://expressjs.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个基于 Node.js + Express + SQLite 的王者荣耀英雄收集统计网站，支持多账号管理、英雄收集标记、实时统计展示等功能。

## ✨ 功能特性

### 用户功能
- 🔐 **用户注册/登录** - JWT + Cookie 持久化认证，7天免登录
- 👤 **个人中心** - 修改资料、密码重置
- 🎮 **多账号管理** - 支持 QQ/微信区，区分安卓/苹果设备
- 🗺️ **自定义区服** - 支持任意区服名称输入
- 🦸 **英雄收集标记** - 点击卡片标记已拥有英雄，实时统计
- 📊 **实时统计展示** - 总数、已收集数、完成百分比、职业分布
- 🔍 **英雄搜索筛选** - 按名称搜索，按职业筛选
- ✨ **批量操作** - 支持多选、框选、全选/取消全选
- 🖼️ **英雄头像展示** - 使用官方英雄头像

### 管理后台
- 👥 **用户管理** - 用户增删改、密码重置
- 🦸 **英雄管理** - 英雄增删改、分页展示（每页10条）、职业筛选、默认英雄设置
- 💾 **数据备份** - 创建备份、导出、导入、恢复、删除备份
- 📈 **系统概览** - 用户统计、英雄统计、备份管理

## 🚀 快速开始

### 环境要求
- Node.js >= 16.0
- npm >= 8.0

### 安装步骤

1. **克隆仓库**
```bash
git clone https://github.com/fantasycat6/Glory_of_Kings_role.git
cd Glory_of_Kings_role
```

2. **安装依赖**
```bash
npm install
```

3. **配置环境变量**
```bash
# 复制示例配置文件
cp .env.example .env

# 编辑 .env 文件，设置 JWT_SECRET
# JWT_SECRET=your-secret-key-here-change-this
```

4. **启动服务**
```bash
# 生产模式
npm start

# 开发模式（需要安装 nodemon）
npm run dev
```

5. **访问网站**
打开浏览器访问 http://localhost:3000

### 默认管理员账号
- 用户名: `admin`
- 密码: `admin123`

> ⚠️ **安全提示**: 部署后请立即修改默认管理员密码！

## 📁 项目结构

```
Glory_of_Kings_role/
├── app.js                  # 主应用入口
├── package.json            # 项目配置
├── package-lock.json       # 依赖锁定
├── README.md               # 项目文档
├── .env.example            # 环境变量示例
├── .gitignore              # Git 忽略配置
├── start.cmd               # Windows 启动脚本
├── data/                   # 数据目录
│   ├── database.db         # SQLite 数据库（自动生成）
│   ├── heroes_official.json # 英雄基础数据
│   └── hero_images.json    # 英雄头像数据
├── backup/                 # 数据备份目录
├── models/                 # 数据模型层
│   └── database.js         # 数据库操作封装
├── views/                  # 视图模板 (EJS)
│   ├── partials/           # 公共组件 (header/footer)
│   ├── admin/              # 管理后台页面
│   └── *.ejs               # 用户页面
├── public/                 # 静态资源
│   ├── css/                # 样式文件
│   ├── js/                 # 脚本文件
│   └── favicon.svg         # 网站图标
└── docs/                   # 文档目录
    └── 王者荣耀英雄与区服数据.xlsx  # 原始数据
```

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| **后端框架** | Node.js + Express 5.x |
| **模板引擎** | EJS |
| **数据库** | SQLite3 (better-sqlite3) |
| **前端框架** | Bootstrap 5 + Bootstrap Icons |
| **认证机制** | bcryptjs + jsonwebtoken + cookie-parser |
| **文件上传** | multer |
| **环境配置** | dotenv |

## 📝 数据说明

### 英雄数据
- 总计 **130** 位英雄（包含 5 个元流之子职业版本）
- 职业分布：

| 职业 | 数量 | 占比 |
|------|------|------|
| 坦克 | 30 | 23% |
| 战士 | 43 | 33% |
| 刺客 | 24 | 18% |
| 法师 | 45 | 35% |
| 射手 | 20 | 15% |
| 辅助 | 22 | 17% |

> 注：部分英雄属于多个职业，总数可能超过 130

### 默认英雄
新注册的账号自动拥有以下英雄：
- **基础英雄**: 亚瑟、妲己、后羿、安琪拉
- **元流之子系列**: 坦克、刺客、法师、射手、辅助 五个职业版本

## 💾 数据备份

### 支持的操作
| 操作 | 说明 |
|------|------|
| 创建备份 | 在服务器本地创建 JSON 格式备份 |
| 导入备份 | 上传本地 JSON 文件恢复数据 |
| 恢复备份 | 从服务器已有备份恢复 |
| 下载备份 | 下载备份文件到本地 |
| 删除备份 | 删除服务器上的备份文件 |

### 恢复模式
- **合并模式**: 保留现有英雄，仅添加备份中不存在的英雄
- **覆盖模式**: 删除所有现有英雄，完全使用备份数据（保留用户收集记录）

## 🔌 API 接口

### 认证相关
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `POST /api/auth/logout` - 用户登出

### 英雄相关
- `GET /api/heroes` - 获取所有英雄列表
- `GET /api/heroes/search?q=关键字` - 搜索英雄
- `POST /api/accounts/:id/heroes/toggle` - 切换英雄拥有状态
- `POST /api/accounts/:id/heroes/batch` - 批量操作英雄

### 账号相关
- `GET /api/accounts` - 获取用户所有游戏账号
- `POST /api/accounts` - 创建游戏账号
- `PUT /api/accounts/:id` - 更新游戏账号
- `DELETE /api/accounts/:id` - 删除游戏账号

### 管理后台
- `GET /api/admin/users` - 获取用户列表
- `POST /api/admin/users` - 创建用户
- `PUT /api/admin/users/:id` - 更新用户
- `DELETE /api/admin/users/:id` - 删除用户
- `GET /api/admin/heroes` - 获取英雄列表（分页）
- `POST /api/admin/heroes` - 添加英雄
- `PUT /api/admin/heroes/:name` - 更新英雄
- `DELETE /api/admin/heroes/:name` - 删除英雄
- `GET /api/admin/backup/list` - 获取备份列表
- `POST /api/admin/backup/create` - 创建备份
- `GET /api/admin/backup/download/:id` - 下载备份
- `POST /api/admin/backup/restore/:id` - 恢复备份
- `POST /api/admin/backup/import` - 导入备份
- `DELETE /api/admin/backup/:id` - 删除备份

## 🔒 安全说明

- ✅ 用户密码使用 **bcrypt** 加密存储
- ✅ **JWT Token** 存储在 httpOnly Cookie 中，有效期 7 天
- ✅ 管理员权限验证中间件
- ✅ **SQL 注入防护** - 使用参数化查询
- ✅ **路径遍历防护** - 备份文件路径校验
- ✅ **XSS 防护** - EJS 模板自动转义输出

## 🚀 部署指南

### 使用 PM2 部署
```bash
# 安装 PM2
npm install -g pm2

# 启动应用
pm2 start app.js --name "glory-of-kings"

# 保存配置
pm2 save
pm2 startup
```

### Docker 部署（可选）
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --production
COPY . .
EXPOSE 3000
CMD ["node", "app.js"]
```

### Nginx 反向代理
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

[MIT License](LICENSE) © 2026 fantasycat6

## 🙏 致谢

- 英雄数据来源：[王者荣耀官网](https://pvp.qq.com)
- 英雄头像来源：腾讯游戏官方资源
- 技术栈：[Node.js](https://nodejs.org/) | [Express](https://expressjs.com/) | [Bootstrap](https://getbootstrap.com/)

---

⭐ 如果这个项目对你有帮助，请点个 Star 支持一下！