# 智能旅游助手前端

这是一个对话式旅行规划页面，提供智能的旅游行程规划服务。

## 项目特点

- 🎨 **现代清爽设计** - 采用清新的旅行配色，避免传统后台管理系统的沉闷感
- 💬 **对话式交互** - 通过自然对话获取用户需求，生成个性化行程
- 📋 **结构化展示** - 清晰展示每日安排、酒店建议、预算分析等信息
- 🧠 **智能记忆** - 支持多轮对话，记住用户的旅行偏好
- 📱 **响应式布局** - 完美适配桌面端和移动端
- ⚡ **TypeScript** - 完整的类型安全保障

## 技术栈

- **React 18.3** - UI 框架
- **TypeScript** - 类型安全
- **Vite** - 构建工具
- **Tailwind CSS v4** - 样式框架
- **Lucide React** - 图标库

## 项目结构

```
/src
├── app
│   ├── components/           # 所有 React 组件
│   │   ├── Header.tsx       # 顶部栏（品牌、会话信息）
│   │   ├── ChatArea.tsx     # 聊天区域（主交互区）
│   │   ├── MessageBubble.tsx # 消息气泡组件
│   │   ├── QuickChips.tsx   # 快捷输入按钮
│   │   ├── ItineraryPanel.tsx # 行程面板容器
│   │   ├── ItineraryOverview.tsx # 行程概览
│   │   ├── DailyPlans.tsx   # 每日计划卡片
│   │   ├── HotelSection.tsx # 酒店建议区域
│   │   ├── BudgetSection.tsx # 预算建议区域
│   │   ├── AlertsSection.tsx # 注意事项区域
│   │   ├── AlternativesSection.tsx # 备选方案区域
│   │   └── MemoryState.tsx  # 会话记忆状态
│   ├── services/            # API 服务
│   │   └── chatApi.ts       # 后端聊天 API 调用
│   ├── types/               # TypeScript 类型定义
│   │   └── travel.ts        # 旅游相关类型
│   └── App.tsx              # 主应用组件
└── styles
    └── app.css              # 应用样式

```

## 组件职责

### 1. Header (Header.tsx)
- 显示产品品牌和说明
- 展示并允许编辑 session_id 和 user_id
- 提供会话管理功能

### 2. ChatArea (ChatArea.tsx)
- 管理消息列表展示
- 处理用户输入和发送
- 显示加载状态
- 提供快捷输入功能

### 3. MessageBubble (MessageBubble.tsx)
- 渲染单条消息（用户或助手）
- 展示追问问题按钮
- 支持点击问题快速输入

### 4. QuickChips (QuickChips.tsx)
- 提供预设的快捷输入选项
- 帮助用户快速开始对话

### 5. ItineraryPanel (ItineraryPanel.tsx)
- 行程展示的容器组件
- 根据状态显示不同内容（等待/需要澄清/完整行程）
- 管理滚动行为

### 6. ItineraryOverview (ItineraryOverview.tsx)
- 展示行程基本信息（目的地、天数、日期、预算等）
- 显示行程概览文字
- 展示天气摘要

### 7. DailyPlans (DailyPlans.tsx)
- 展示每日详细安排
- 分上午、下午、晚上三个时段
- 显示每日亮点标签

### 8. HotelSection (HotelSection.tsx)
- 展示推荐住宿区域
- 显示酒店候选列表
- 展示酒店特色标签

### 9. BudgetSection (BudgetSection.tsx)
- 展示预算评估等级
- 提供预算建议说明

### 10. AlertsSection (AlertsSection.tsx)
- 展示旅行注意事项
- 用醒目样式提醒用户

### 11. AlternativesSection (AlternativesSection.tsx)
- 展示备选旅行方案
- 提供多样化选择

### 12. MemoryState (MemoryState.tsx)
- 展示当前会话的短期记忆
- 显示已识别的旅行参数
- 展示用户偏好标签

### 13. App.tsx
- 主应用容器
- 管理全局状态（消息、行程、会话状态）
- 协调各组件交互
- 处理 API 调用和错误

## API 接口

### 后端接口地址
- 默认：`http://localhost:8000/chat`
- 可通过环境变量 `VITE_API_URL` 配置

### 请求格式
```json
{
  "message": "帮我安排一个大连3天情侣游，5月20号出发，预算3000",
  "session_id": "demo-session",
  "user_id": "demo-user"
}
```

### 响应格式
```json
{
  "session_id": "demo-session",
  "user_id": "demo-user",
  "user_input": "...",
  "answer": "自然语言旅行建议",
  "structured_itinerary": {
    "status": "ready",
    "destination": "大连",
    "days": 3,
    "date": "2026-05-20",
    "companions": "情侣",
    "budget": 3000,
    "overview": "...",
    "daily_plans": [...],
    "hotel_suggestion": {...},
    "budget_advice": {...},
    "alerts": [...],
    "alternatives": [...]
  },
  "session_state": {
    "city": "大连",
    "days": 3,
    "date": "2026-05-20",
    "budget": 3000,
    "companions": "情侣"
  }
}
```

## 启动步骤

### 1. 配置后端 API 地址

复制 `.env.example` 为 `.env`：
```bash
cp .env.example .env
```

编辑 `.env` 文件，设置后端 API 地址：
```
VITE_API_URL=http://localhost:8000
```

### 2. 安装依赖

```bash
pnpm install
```

### 3. 启动开发服务器

```bash
pnpm dev
```

### 4. 构建生产版本

```bash
pnpm build
```

## 主要功能

### 1. 多轮对话
- 支持连续对话，保持上下文
- 自动记忆用户偏好和旅行参数

### 2. 智能追问
- 当信息不足时，展示追问问题
- 点击问题可快速输入

### 3. 结构化展示
- 清晰的行程概览
- 每日详细安排（上午/下午/晚上）
- 酒店和预算建议
- 注意事项和备选方案

### 4. 会话管理
- 可自定义 session_id 和 user_id
- 支持多个独立会话
- localStorage 持久化会话信息

### 5. 响应式设计
- 桌面端：左右分栏布局
- 移动端：上下布局，可折叠行程面板
- 平滑的过渡动画

### 6. 错误处理
- 友好的错误提示
- 网络错误自动检测
- 点击关闭错误提示

## 设计特色

### 配色方案
- **主色调**：天空蓝 (#0ea5e9) - 象征旅行和自由
- **次要色**：琥珀色 (#f59e0b) - 象征阳光和活力
- **成功色**：翠绿色 (#10b981)
- **警告色**：琥珀色 (#f59e0b)
- **危险色**：红色 (#ef4444)

### 视觉特点
- 大量使用圆角和阴影，营造柔和感
- 渐变背景突出重点信息
- 悬浮动效增强交互反馈
- 清晰的信息层次和留白

### 动画效果
- 消息淡入动画
- 按钮悬浮和缩放
- 平滑的滚动行为
- Loading 旋转动画

## 开发建议

### 修改后端地址
编辑 `.env` 文件或在 `/src/app/services/chatApi.ts` 中直接修改 `API_BASE_URL`

### 添加新的快捷输入
编辑 `/src/app/components/QuickChips.tsx` 中的 `QUICK_SUGGESTIONS` 数组

### 自定义主题色
编辑 `/src/styles/app.css` 中的 CSS 变量

### 扩展消息类型
在 `/src/app/types/travel.ts` 中添加新的类型定义

## 注意事项

1. **后端依赖**：前端需要后端 API 正常运行才能工作
2. **CORS 配置**：确保后端允许前端域名的跨域请求
3. **环境变量**：生产环境需要正确配置 `VITE_API_URL`
4. **浏览器兼容性**：建议使用现代浏览器（Chrome, Firefox, Safari, Edge）

## 常见问题

### Q: 无法连接到服务器
A: 检查后端是否启动，确认 `.env` 中的 `VITE_API_URL` 配置正确

### Q: 消息发送后没有响应
A: 检查浏览器控制台的网络请求，查看后端返回的错误信息

### Q: 样式显示异常
A: 清除浏览器缓存，重新启动开发服务器

### Q: 移动端布局错乱
A: 确保使用现代浏览器，检查是否有 CSS 兼容性问题

## 后续优化建议

1. **性能优化**
   - 消息虚拟滚动（处理大量历史消息）
   - 图片懒加载
   - 组件代码分割

2. **功能增强**
   - 支持导出行程为 PDF
   - 添加地图展示
   - 支持行程分享
   - 添加语音输入

3. **用户体验**
   - 添加打字机效果
   - 支持消息编辑和删除
   - 添加快捷键支持
   - 支持暗黑模式

4. **数据管理**
   - 集成状态管理库（如 Zustand）
   - 添加离线缓存
   - 支持历史会话查看

## License

MIT
