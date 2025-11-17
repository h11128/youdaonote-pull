// 有道云笔记Cookie提取工具
// 在已登录的有道云笔记页面的浏览器控制台中运行此代码

function extractYoudaoNoteCookies() {
    // 需要提取的cookie名称
    const requiredCookies = ['YNOTE_CSTK', 'YNOTE_LOGIN', 'YNOTE_SESS'];
    
    // 获取所有cookie
    const cookies = document.cookie.split(';');
    const cookieMap = {};
    
    // 解析cookie
    cookies.forEach(cookie => {
        const [name, value] = cookie.trim().split('=');
        if (name && value) {
            cookieMap[name] = value;
        }
    });
    
    // 构建cookies.json格式的数据
    const cookiesData = {
        cookies: []
    };
    
    // 检查并添加必需的cookie
    requiredCookies.forEach(cookieName => {
        if (cookieMap[cookieName]) {
            cookiesData.cookies.push([
                cookieName,
                cookieMap[cookieName],
                ".note.youdao.com",
                "/"
            ]);
            console.log(`✅ 找到 ${cookieName}: ${cookieMap[cookieName]}`);
        } else {
            console.log(`❌ 未找到 ${cookieName}`);
        }
    });
    
    if (cookiesData.cookies.length === 3) {
        console.log('\n🎉 成功提取所有必需的cookie！');
        console.log('\n请复制以下内容到 cookies.json 文件中：');
        console.log('\n' + JSON.stringify(cookiesData, null, 4));
        
        // 尝试复制到剪贴板
        try {
            navigator.clipboard.writeText(JSON.stringify(cookiesData, null, 4));
            console.log('\n📋 已自动复制到剪贴板！');
        } catch (e) {
            console.log('\n⚠️ 无法自动复制到剪贴板，请手动复制上面的内容');
        }
        
        return cookiesData;
    } else {
        console.log('\n❌ 未能提取到所有必需的cookie，请确保您已经登录有道云笔记');
        return null;
    }
}

// 运行提取函数
console.log('🔍 开始提取有道云笔记Cookie...');
console.log('📍 当前页面URL:', window.location.href);

// 检查是否在有道云笔记域名下
if (window.location.hostname.includes('youdao.com')) {
    extractYoudaoNoteCookies();
} else {
    console.log('❌ 请在有道云笔记页面 (*.youdao.com) 运行此脚本');
}
