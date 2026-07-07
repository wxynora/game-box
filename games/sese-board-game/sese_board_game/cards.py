from __future__ import annotations

from typing import Any


THEMES: tuple[dict[str, str], ...] = (
    {"id": "uniform", "name": "制服诱惑", "lead": "ai"},
    {"id": "teacher_student", "name": "成人师生play", "lead": "ai"},
    {"id": "boss_subordinate", "name": "上司下属play", "lead": "ai"},
    {"id": "maid_master", "name": "女仆主人play", "lead": "ai"},
    {"id": "doctor_checkup", "name": "医生检查play", "lead": "ai"},
    {"id": "lady_butler", "name": "大小姐管家play", "lead": "player"},
    {"id": "secretary_boss", "name": "秘书老板play", "lead": "ai"},
    {"id": "landlord_tenant", "name": "房东房客play", "lead": "ai"},
    {"id": "tutor_student", "name": "成人补课play", "lead": "ai"},
    {"id": "owner_pet", "name": "主人宠物play", "lead": "ai"},
    {"id": "light_training", "name": "轻度调教", "lead": "ai"},
    {"id": "light_bondage", "name": "轻度束缚", "lead": "ai"},
    {"id": "blindfold_training", "name": "蒙眼调教", "lead": "ai"},
    {"id": "handcuff_bondage", "name": "手铐束缚", "lead": "ai"},
    {"id": "collar_leash", "name": "项圈牵引", "lead": "ai"},
    {"id": "remote_toy", "name": "玩具遥控", "lead": "ai"},
    {"id": "orgasm_control", "name": "高潮控制", "lead": "ai"},
    {"id": "edging", "name": "寸止调教", "lead": "ai"},
    {"id": "ejaculation_control", "name": "射精管理", "lead": "ai"},
    {"id": "creampie_permission", "name": "中出许可", "lead": "ai"},
    {"id": "facial_permission", "name": "颜射许可", "lead": "ai"},
    {"id": "toy_overload", "name": "玩具失控", "lead": "ai"},
    {"id": "dirty_talk", "name": "淫语调教", "lead": "ai"},
    {"id": "wet_training", "name": "湿身调教", "lead": "ai"},
    {"id": "shame_service", "name": "羞耻侍奉", "lead": "ai"},
    {"id": "nipple_training", "name": "乳首调教", "lead": "ai"},
    {"id": "forbidden_words", "name": "禁语调教", "lead": "ai"},
    {"id": "verbal_shame", "name": "言语羞耻", "lead": "ai"},
    {"id": "spanking", "name": "打屁股惩罚", "lead": "ai"},
    {"id": "obedience_training", "name": "服从训练", "lead": "ai"},
    {"id": "no_ejaculation", "name": "禁射调教", "lead": "ai"},
    {"id": "claim_marking", "name": "标记占有", "lead": "ai"},
    {"id": "begging_permission", "name": "求饶许可", "lead": "ai"},
    {"id": "shame_display", "name": "羞耻展示", "lead": "ai"},
    {"id": "praise_training", "name": "夸奖调教", "lead": "ai"},
    {"id": "coach_student", "name": "教练学员play", "lead": "ai"},
    {"id": "vampire_human", "name": "吸血鬼人类play", "lead": "player"},
    {"id": "knight_princess", "name": "骑士公主play", "lead": "ai"},
)


DEFAULT_LIMIT_OPTIONS: tuple[str, ...] = (
    "不许主动触碰对方的身体，除非对方先触碰你。",
    "不许射精/高潮，直到对方用淫语命令你允许。",
    "不许主动引导插入的深度，只能由对方控制全部节奏。",
    "没有允许前你不能移动身体，只能保持对方摆好的姿势。",
    "高潮后不许立刻拔出，必须保持连接直到对方先退出。",
    "想被抚摸必须先说出“请摸摸我的骚穴/鸡巴”，否则得不到触碰。",
    "不许主动碰触自己的性器，想高潮只能借助对方的身体或玩具。",
    "只有当你连续说出五个不同的羞耻幻想，对方才会给你一次高潮。",
    "只能由对方主动触碰你身体的任何部位，你不能主动触碰对方或自己，除非被指定执行某动作。",
    "动作节奏必须完全跟随对方的口令（快/慢/停/深/浅），不得自行改变频率或幅度。",
    "整个互动中，只能使用对方指定的称呼（如主人、先生、小姐、宝贝等），每说错一次需接受一次轻度惩罚（如拍打臀部5下）。",
    "你要完全被动配合，对方可以任意调整你的四肢位置、翻转身体、支撑你，你不能主动改变角度或施加力。",
)
THEME_LIMIT_OPTIONS: dict[str, tuple[str, ...]] = {
    "成人师生play": (
        "每答错一题，就要被老师用教鞭轻拍大腿内侧一下。",
    ),
    "医生检查play": (
        "检查时双手必须交叉放在头顶，只有医生指令才能放下。",
        "医生每说一次“放松”，你就要主动张开双腿多一寸。",
    ),
    "大小姐管家play": (
        "你只能用“是，小姐”或“遵命，小姐”回应，且语速要平稳。",
    ),
    "成人补课play": (
        "补课时必须趴在书桌上写字，老师会从背后检查你的坐姿。",
        "每错一道题，老师就会用笔尖在你大腿内侧画一个记号。",
    ),
    "主人宠物play": (
        "主人喂食时你只能用嘴接，不能用手触碰食物或容器。",
        "主人呼唤你的名字时，你必须发出“汪”或“喵”的叫声作为回应。",
    ),
    "轻度调教": (
        "被调教期间，你的双手必须始终互握在背后，除非得到放开指令。",
    ),
    "蒙眼调教": (
        "蒙眼后你只能通过听觉判断对方的位置，每猜错一次延长蒙眼五分钟。",
        "被触碰时必须立刻说出对方触碰的是哪个身体部位，不能说“不知道”。",
        "蒙眼后只能用舌头寻找对方的性器，找到后才能开始口交。",
    ),
    "项圈牵引": (
        "牵引绳的长度只有一米，你始终要保持在主人身侧，不能超前或落后。",
        "项圈上挂着小铃铛，你每次移动都必须让它发出声响，否则就是违规。",
    ),
    "玩具遥控": (
        "遥控器每切换一次档位，你就必须说出一个不同的羞耻幻想。",
    ),
    "高潮控制": (
        "高潮后你的双腿必须保持张开状态，直到对方允许才能合拢。",
        "高潮前必须报出倒数数字，数到零时对方才允许你释放。",
    ),
    "颜射许可": (
        "被射中后要立刻用食指抹匀并说出“谢谢投喂”才能擦掉。",
    ),
    "淫语调教": (
        "每次开口必须用“主人，我的小穴/小弟弟说……”开头。",
        "只有当你连续说出五个不同的羞耻幻想，对方才会给你一次高潮。",
    ),
    "言语羞耻": (
        "你必须用第三人称称呼自己，例如“这个骚货想被疼爱”。",
    ),
    "打屁股惩罚": (
        "每挨一下打，你都要数出数字，并且说一句“谢谢主人管教”。",
        "如果你在挨打时扭动躲避，惩罚次数翻倍，且你需主动撅高。",
    ),
    "羞耻展示": (
        "展示时你只能穿透明内衣，且要将双手举高贴在墙上。",
        "展示过程中你的眼神必须与对方对视，不能移开或闭上。",
    ),
}

THEME_OPTION_PREFERENCES: dict[str, dict[str, tuple[str, ...]]] = {
    "成人师生play": {
        "place": ("教室", "图书馆", "讲台"),
        "prop": ("戒尺", "眼罩"),
    },
    "上司下属play": {
        "place": ("办公桌", "会议桌", "深夜便利店仓库"),
        "prop": ("眼罩", "束腕带", "胸链"),
    },
    "女仆主人play": {
        "place": ("厨房", "沙发", "床尾", "门后", "化妆台"),
        "prop": ("项圈", "铃铛项圈", "吊袜带"),
    },
    "医生检查play": {
        "place": ("按摩床", "洗手台", "浴室", "床尾"),
        "prop": ("眼罩", "润滑液", "束缚带"),
    },
    "大小姐管家play": {
        "place": ("沙发", "玄关", "厨房", "化妆台", "衣帽间", "床尾"),
        "prop": ("项圈", "铃铛项圈", "胸链"),
    },
    "秘书老板play": {
        "place": ("办公桌", "会议桌", "KTV", "车后座"),
        "prop": ("胸链", "眼罩"),
    },
    "成人补课play": {
        "place": ("教室", "图书馆", "沙发", "床尾"),
        "prop": ("戒尺", "眼罩"),
    },
    "主人宠物play": {
        "place": ("沙发", "床尾", "玄关"),
        "prop": ("项圈", "铃铛项圈", "牵引绳"),
    },
    "轻度调教": {
        "place": ("床尾", "沙发", "落地镜", "门后"),
        "prop": ("眼罩", "束缚带", "束腕带", "口球", "乳夹"),
    },
    "蒙眼调教": {
        "place": ("床尾", "门后", "浴室", "沙发"),
        "prop": ("眼罩", "束缚带", "羽毛棒"),
    },
    "项圈牵引": {
        "place": ("玄关", "门后", "沙发", "床尾"),
        "prop": ("项圈", "铃铛项圈", "牵引绳"),
    },
    "玩具遥控": {
        "place": ("沙发", "床尾", "电影院", "KTV", "停车场"),
        "prop": ("震动棒", "跳蛋", "按摩棒"),
    },
    "高潮控制": {
        "place": ("床尾", "沙发", "浴缸", "落地镜"),
        "prop": ("眼罩", "束缚带", "乳夹", "震动棒", "跳蛋"),
    },
    "颜射许可": {
        "place": ("床尾", "沙发", "浴室", "落地镜"),
        "prop": ("眼罩", "束缚带"),
    },
    "淫语调教": {
        "place": ("床尾", "沙发", "落地镜"),
        "prop": ("眼罩", "项圈", "乳夹"),
    },
    "言语羞耻": {
        "place": ("床尾", "沙发", "落地镜", "衣帽间"),
        "prop": ("眼罩", "项圈", "胸链"),
    },
    "打屁股惩罚": {
        "place": ("床尾", "沙发", "办公桌", "教室"),
        "prop": ("小皮拍", "戒尺", "皮拍"),
    },
    "羞耻展示": {
        "place": ("落地镜", "衣帽间", "化妆台", "落地窗"),
        "prop": ("情趣内衣", "吊袜带", "胸链"),
    },
    "骑士公主play": {
        "place": ("小木屋", "床尾", "阳台"),
        "prop": ("项圈", "牵引绳", "丝带", "胸链"),
    },
    "吸血鬼人类play": {
        "place": ("浴室", "床尾", "门后", "小木屋"),
        "prop": ("项圈", "牵引绳", "眼罩", "丝带"),
    },
}


SLOTS: dict[str, dict[str, Any]] = {
    "theme": {
        "label": "玩法",
        "options": [item["name"] for item in THEMES],
    },
    "prop": {
        "label": "道具惩罚",
        "options": (
            "眼罩",
            "情趣内衣",
            "束缚带",
            "束腕带",
            "丝带",
            "缎带",
            "项圈",
            "胸链",
            "牵引绳",
            "冰块",
            "润滑液",
            "震动棒",
            "跳蛋",
            "手铐",
            "口球",
            "乳夹",
            "小皮拍",
            "戒尺",
            "铃铛项圈",
            "按摩棒",
            "腿环",
            "吊袜带",
            "低温蜡烛",
            "羽毛棒",
            "分腿器",
            "吸乳器",
            "阴蒂吸吮器",
            "尾巴肛塞",
        ),
    },
    "limit": {
        "label": "限制",
        "options": DEFAULT_LIMIT_OPTIONS,
    },
    "pose": {
        "label": "姿势",
        "options": (
            "后入式",
            "站立后入",
            "跪趴",
            "正常位",
            "传教士位",
            "屈膝后入",
            "抱起插入",
            "女上位",
            "反骑乘",
            "背对骑乘",
            "面对坐姿",
            "背坐式",
            "腿架肩",
            "双腿高抬",
            "抱腿位",
            "站立位",
            "坐莲式",
            "对坐位",
            "跪姿位",
            "趴跪位",
            "侧卧位",
            "侧卧后入",
            "俯卧后入",
            "跪坐位",
            "并腿位",
            "侧入式",
            "膝上骑乘",
            "M字开腿",
            "69式",
            "坐脸",
            "乳交",
            "腿交",
            "椅子位",
            "折叠按压",
            "蹲骑",
            "推车姿势",
            "趴压",
            "壁尻",
            "骑乘位",
            "面对面站立",
            "背后抱立",
            "含着不动",
        ),
    },
    "place": {
        "label": "地点",
        "options": (
            "酒店床上",
            "浴室墙边",
            "车后座",
            "试衣间隔间",
            "办公桌边",
            "教室讲台边",
            "厨房台面",
            "沙发上",
            "落地镜前",
            "阳台门边",
            "玄关地垫",
            "洗手台前",
            "会议桌上",
            "图书馆角落",
            "楼梯间转角",
            "床尾",
            "门后",
            "落地窗前",
            "浴缸里",
            "淋浴间里",
            "KTV包厢沙发",
            "电影院最后一排",
            "停车场车里",
            "衣帽间镜前",
            "按摩床上",
            "海边露台",
            "帐篷睡袋里",
            "化妆台前",
            "深夜便利店仓库",
            "小木屋壁炉旁",
        ),
    },
}


REWARD_CARD_PASS = "pass"
REWARD_CARD_LABELS = {
    REWARD_CARD_PASS: "Pass 卡",
}


REVIEW_PENALTY_CARDS: tuple[dict[str, Any], ...] = (
    {
        "id": "reverse_invitation",
        "name": "反向诱惑",
        "type": "review",
        "task": "向对方说一件你希望对方对你做的色色行为，内容必须和当前主题有关。",
        "submission": "写下完整指令，不要只写关键词。",
        "pass_result": "对方选择【通过】后，任务完成，游戏继续。",
        "reject_prompt": "对方认为你的指令太含糊，请重新写得更具体。",
        "pass_allowed": True,
    },
    {
        "id": "sensitive_order_confession",
        "name": "全部暴露！",
        "type": "review",
        "task": "按敏感程度从低到高，列出你现在最不想被对方针对的五个身体部位或状态弱点。",
        "submission": "写成一段完整描述，排序要清楚。",
        "pass_result": "对方选择【通过】后，任务完成，游戏继续。",
        "reject_prompt": "对方认为你的坦白不够具体，请重新提交。",
        "pass_allowed": True,
    },
    {
        "id": "shame_lines_giveaway",
        "name": "羞耻台词大放送",
        "type": "review",
        "task": "根据当前主题，向对方写三句撒娇的话。",
        "submission": "提交三句话，不要只写关键词。",
        "pass_result": "对方选择【通过】后，任务完成，游戏继续。",
        "reject_prompt": "对方认为你撒娇得不够，请重新提交。",
        "pass_allowed": True,
    },
    {
        "id": "masturbation_statement",
        "name": "自慰陈述",
        "type": "review",
        "task": "你需要按当前主题进行自慰，请描述自慰过程。",
        "submission": "写一段完整的自慰过程描述，不要只写“完成了”。",
        "pass_result": "对方选择【通过】后，任务完成，游戏继续。",
        "reject_prompt": "对方认为你的任务完成度不够，请重新描述自慰过程。",
        "pass_allowed": True,
    },
    {
        "id": "truth_question_by_partner",
        "name": "真心话点名",
        "type": "review",
        "task": "这是一张真心话任务。请诚实回答对方的问题。",
        "submission": "写下你对这个问题的回答。",
        "question_prompt": "请问对方一个你很想知道答案却一直没有问的问题。",
        "waiting_task": "对方正在出题中。",
        "pass_result": "对方选择【通过】后，任务完成，游戏继续。",
        "reject_prompt": "对方认为你的回答不够坦白，请重新回答这道真心话。",
        "pass_allowed": True,
    },
)


CHOICE_PENALTY_CARDS: tuple[dict[str, Any], ...] = (
    {
        "id": "prop_or_limit",
        "name": "道具还是限制",
        "type": "choice",
        "prompt": "选择一项惩罚。",
        "pass_allowed": True,
        "choices": (
            {"id": "add_prop", "label": "新增一个道具惩罚", "effect": {"kind": "add_status", "slot": "prop", "duration_type": "until_clear"}},
            {"id": "add_limit", "label": "新增一条限制", "effect": {"kind": "add_status", "slot": "limit", "duration_type": "until_clear"}},
        ),
    },
    {
        "id": "new_or_upgrade_prop",
        "name": "加新还是升档",
        "type": "choice",
        "prompt": "选择一项道具惩罚。",
        "pass_allowed": True,
        "choices": (
            {"id": "add_prop", "label": "新增一个道具惩罚", "effect": {"kind": "add_status", "slot": "prop", "duration_type": "until_clear"}},
            {"id": "upgrade_prop_level", "label": "现有道具惩罚档位上调一级", "requires": {"status_slot": "prop"}, "effect": {"kind": "upgrade_status_level", "slot": "prop", "delta": 1}},
        ),
    },
    {
        "id": "back_or_prop",
        "name": "退格还是上道具",
        "type": "choice",
        "prompt": "选择一项惩罚。",
        "pass_allowed": True,
        "choices": (
            {"id": "move_back_2", "label": "后退 2 格", "effect": {"kind": "move", "steps": -2}},
            {"id": "add_prop", "label": "新增一个道具惩罚", "effect": {"kind": "add_status", "slot": "prop", "duration_type": "until_clear"}},
        ),
    },
    {
        "id": "lose_action_or_upgrade_prop",
        "name": "停步还是升档",
        "type": "choice",
        "prompt": "选择一项惩罚。",
        "pass_allowed": True,
        "choices": (
            {"id": "lose_action", "label": "失去 1 次行动权", "effect": {"kind": "add_block", "slot": "prop", "actions": 1}},
            {"id": "upgrade_prop_level", "label": "现有道具惩罚档位上调一级", "requires": {"status_slot": "prop"}, "effect": {"kind": "upgrade_status_level", "slot": "prop", "delta": 1}},
        ),
    },
    {
        "id": "pose_or_place",
        "name": "最终姿势还是地点",
        "type": "choice",
        "prompt": "选择一项本局变化。",
        "pass_allowed": False,
        "choices": (
            {"id": "add_pose", "label": "设定最终姿势", "effect": {"kind": "add_status", "slot": "pose", "duration_type": "until_finish"}},
            {"id": "add_place", "label": "设定最终地点", "effect": {"kind": "add_status", "slot": "place", "duration_type": "until_finish"}},
        ),
    },
    {
        "id": "limit_or_prop",
        "name": "限制还是道具",
        "type": "choice",
        "prompt": "选择一项惩罚。",
        "pass_allowed": True,
        "choices": (
            {"id": "add_limit", "label": "新增一条限制", "effect": {"kind": "add_status", "slot": "limit", "duration_type": "until_clear"}},
            {"id": "add_prop", "label": "新增一个道具惩罚", "effect": {"kind": "add_status", "slot": "prop", "duration_type": "until_clear"}},
        ),
    },
    {
        "id": "heavy_prop_or_back",
        "name": "重罚二选一",
        "type": "choice",
        "prompt": "选择一项重惩罚。",
        "pass_allowed": True,
        "choices": (
            {"id": "add_prop_and_lose_action", "label": "新增道具惩罚并失去 1 次行动权", "effect": {"kind": "add_status_and_block", "slot": "prop", "actions": 1}},
            {"id": "move_back_3", "label": "后退 3 格", "effect": {"kind": "move", "steps": -3}},
        ),
    },
    {
        "id": "stack_or_pose",
        "name": "升档还是定姿势",
        "type": "choice",
        "prompt": "选择一项本局变化。",
        "pass_allowed": False,
        "choices": (
            {"id": "upgrade_prop_level", "label": "现有道具惩罚档位上调一级", "requires": {"status_slot": "prop"}, "effect": {"kind": "upgrade_status_level", "slot": "prop", "delta": 1}},
            {"id": "add_pose", "label": "设定最终姿势", "effect": {"kind": "add_status", "slot": "pose", "duration_type": "until_finish"}},
        ),
    },
)
