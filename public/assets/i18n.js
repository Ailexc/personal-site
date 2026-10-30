/* 中英文案（内容与 index.html 的 data-i18n 键一一对应） */
window.I18N = {
  zh: {
    "nav.work": "作品",
    "nav.contact": "联系",

    "hero.eyebrow": "求职中 · 北京 · 可出差 · 8 年经验",
    "hero.title": "AI Agent 工程 · 平台工程",
    "hero.fact.platform": "平台工程",
    "hero.tag.auth": "统一认证",
    "hero.tag.iam": "权限中心",
    "hero.tag.release": "发布系统",
    "hero.tag.event": "事件管理",
    "hero.tag.ticket": "工单中心",
    "hero.tag.cloud": "多云管理",
    "hero.fact.backend": "后端开发",
    "hero.tag.distributed": "分布式",
    "hero.tag.microservice": "微服务",
    "hero.tag.multiagent": "多 Agent 编排",
    "hero.tag.streaming": "流式对话",
    "hero.tag.toolcall": "工具调用",
    "hero.tag.tokencost": "Token 成本控制",
    "hero.fact.fullstack": "全栈交付",
    "hero.fact.path": "工作经历",
    "hero.fact.pathValue": "网络与服务器运维 → 后端开发 → DevOps 平台 → Agent",
    "hero.role1": "AI Agent 工程（转岗中）",
    "hero.role2": "DevOps / 平台开发",
    "hero.role3": "全栈开发",
    "hero.ctaWork": "查看作品",
    "hero.ctaDemo": "在线 Demo",
    "hero.ctaResume": "下载简历",

    "stats.years": "年工程经验",
    "stats.systems": "个可运行系统",
    "stats.ai": "个 AI 项目",


    "facts.location": "所在地",
    "facts.locationValue": "北京 · 可出差",
    "facts.experience": "经验",
    "facts.experienceValue": "8 年",
    "facts.focus": "方向",
    "facts.focusValue": "AI Agent / 平台工程",
    "facts.status": "状态",
    "facts.statusValue": "求职中",


    "work.title": "精选项目",
    "work.viewRepo": "查看仓库 →",
    "work.viewIntro": "查看介绍页 →",
    "work.viewLive": "在线预览 →",
    "work.devops.kicker": "独立设计与开发 · 七个系统",
    "work.devops.desc": "七套内部系统 + 统一网关 + 共享数据层，串成「登录 → 权限 → 资源 → 发布 → 事件 → 工单」一条完整链路。统一身份、权限模型、多云适配都在其中。",
    "work.devops.h1": "<b>统一身份：</b>RS256 JWT + 网关 forwardAuth + OIDC 授权码，七系统单点登录。",
    "work.devops.h2": "<b>权限模型演进：</b>从「用户—应用—环境」三元组实例授权，重构为资源树 + 策略授权的 ABAC-Lite。",
    "work.devops.h3": "<b>数据底座抽象：</b><code>CmdbQuerySet</code> 让 CMDB 像 Django ORM 一样被业务消费。",
    "work.devops.h4": "<b>多云适配：</b>Provider 注册表 + 元数据驱动，新增云厂商 = 一个类 + 一行注册。",
    "work.cumi.kicker": "多 Agent 编排 · 2026",
    "work.cumi.desc": "私人 AI 助理团队：AG2 多 Agent 编排 + WebSocket 流式 + ChromaDB 记忆。",
    "work.review.kicker": "多 Agent 协作 · 2026",
    "work.review.desc": "CrewAI Flows 编排 6 个专业 Agent，Semgrep / Ruff / ESLint 真实工具链。",
    "work.anytra.kicker": "AI 信息中枢 · 2026",
    "work.anytra.desc": "多源输入 → 模型整理 → 自动生成飞书文档。",




    "contact.title": "联系我",
    "contact.email": "邮箱",
    "contact.emailAlt": "备用邮箱",
    "contact.wechat": "微信",
    "contact.qrHint": "点击查看二维码",
    "contact.qrNote": "添加时请备注来意",
    "contact.gitee": "代码托管（Gitee）",
    "contact.github": "GitHub（备用）",

    "footer.note": "用静态页面手工写成 · 无框架 · 无追踪"
  },

  en: {
    "nav.work": "Work",
    "nav.contact": "Contact",

    "hero.eyebrow": "Open to work · Beijing · Available for travel · 8 yrs",
    "hero.title": "AI Agent Engineering · Platform Engineering",
    "hero.fact.platform": "Platform",
    "hero.tag.auth": "Unified Auth",
    "hero.tag.iam": "IAM",
    "hero.tag.release": "Release",
    "hero.tag.event": "Events",
    "hero.tag.ticket": "Ticketing",
    "hero.tag.cloud": "Multi-cloud",
    "hero.fact.backend": "Backend",
    "hero.tag.distributed": "Distributed",
    "hero.tag.microservice": "Microservices",
    "hero.tag.multiagent": "Multi-agent",
    "hero.tag.streaming": "Streaming",
    "hero.tag.toolcall": "Tool calling",
    "hero.tag.tokencost": "Token cost control",
    "hero.fact.fullstack": "Full-stack",
    "hero.fact.path": "Path",
    "hero.fact.pathValue": "Network & server ops → Backend → DevOps platform → AI agents",
    "hero.role1": "AI Agent Engineering (transitioning)",
    "hero.role2": "DevOps / Platform",
    "hero.role3": "Full-stack",
    "hero.ctaWork": "View work",
    "hero.ctaDemo": "Live demo",
    "hero.ctaResume": "Download CV",

    "stats.years": "years in engineering",
    "stats.systems": "runnable systems",
    "stats.ai": "AI projects",


    "facts.location": "Location",
    "facts.locationValue": "Beijing · open to travel",
    "facts.experience": "Experience",
    "facts.experienceValue": "8 years",
    "facts.focus": "Focus",
    "facts.focusValue": "AI Agents / Platform",
    "facts.status": "Status",
    "facts.statusValue": "Open to work",


    "work.title": "Selected work",
    "work.viewRepo": "View repository →",
    "work.viewIntro": "Read case study →",
    "work.viewLive": "Live demo →",
    "work.devops.kicker": "Designed and built solo · seven systems",
    "work.devops.desc": "Seven internal systems with a shared gateway and data layer, connected into one flow: login → permissions → resources → releases → events → tickets. Unified identity, permission model, and multi-cloud adaptation all live here.",
    "work.devops.h1": "<b>Unified identity:</b> RS256 JWT + gateway forwardAuth + OIDC authorization code, single sign-on across seven systems.",
    "work.devops.h2": "<b>Permission model evolution:</b> from user–app–environment tuple grants to a resource-tree + policy ABAC-Lite model.",
    "work.devops.h3": "<b>Data abstraction:</b> <code>CmdbQuerySet</code> exposes CMDB through a Django-ORM-like interface.",
    "work.devops.h4": "<b>Multi-cloud adapter:</b> provider registry + metadata-driven; a new cloud is one class and one registration line.",
    "work.cumi.kicker": "Multi-agent orchestration · 2026",
    "work.cumi.desc": "A personal AI assistant team: AG2 multi-agent orchestration, WebSocket streaming, and ChromaDB memory.",
    "work.review.kicker": "Multi-agent collaboration · 2026",
    "work.review.desc": "CrewAI Flows orchestrating six specialist agents with real Semgrep / Ruff / ESLint tooling.",
    "work.anytra.kicker": "AI information hub · 2026",
    "work.anytra.desc": "Multi-source input → model curation → automatically generated Feishu documents.",




    "contact.title": "Contact",
    "contact.email": "Email",
    "contact.emailAlt": "Alternative email",
    "contact.wechat": "WeChat",
    "contact.qrHint": "Click to show QR code",
    "contact.qrNote": "Please mention how you found me",
    "contact.gitee": "Code (Gitee)",
    "contact.github": "GitHub (backup)",

    "footer.note": "Hand-written static site · no framework · no tracking"
  }
};
