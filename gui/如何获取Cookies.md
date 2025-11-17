# 如何获取有道云笔记 Cookies

当你看到"认证失败"或"Cookies已过期"的错误时，需要重新获取cookies.json文件。

## 方法一：使用浏览器开发者工具（推荐）

### 1. 登录有道云笔记
- 打开浏览器，访问 https://note.youdao.com
- 登录你的有道云笔记账号

### 2. 打开开发者工具
- 按 `F12` 键（或右键点击页面 → 检查）
- 切换到 **Console（控制台）** 标签页

### 3. 执行以下代码

复制以下代码，粘贴到控制台中，按回车执行：

```javascript
(function() {
    var cookies = document.cookie.split(';');
    var cookieArray = [];
    var requiredCookies = ['YNOTE_CSTK', 'YNOTE_SESS', 'YNOTE_LOGIN'];
    
    cookies.forEach(function(cookie) {
        var parts = cookie.trim().split('=');
        var name = parts[0];
        var value = parts.slice(1).join('=');
        
        if (requiredCookies.includes(name)) {
            cookieArray.push([name, value, '.note.youdao.com', '/']);
        }
    });
    
    var result = {
        "cookies": cookieArray
    };
    
    console.log('复制以下内容到 cookies.json 文件：');
    console.log(JSON.stringify(result, null, 2));
    
    // 自动复制到剪贴板
    var text = JSON.stringify(result, null, 2);
    navigator.clipboard.writeText(text).then(function() {
        console.log('✅ 已自动复制到剪贴板！');
    }).catch(function() {
        console.log('⚠️ 自动复制失败，请手动复制上面的内容');
    });
})();
```

### 4. 保存到文件
- 控制台会显示cookies内容，并自动复制到剪贴板
- 打开项目根目录的 `cookies.json` 文件
- 粘贴内容并保存

### 5. 重新启动GUI
- 关闭当前的GUI窗口
- 重新运行 `python start_gui.py`

## 方法二：使用浏览器扩展

### Chrome/Edge 用户
1. 安装 "EditThisCookie" 或 "Cookie-Editor" 扩展
2. 登录 note.youdao.com
3. 点击扩展图标
4. 导出cookies（选择JSON格式）
5. 手动提取 YNOTE_CSTK、YNOTE_SESS、YNOTE_LOGIN 三个cookie
6. 按照以下格式保存到 cookies.json：

```json
{
  "cookies": [
    ["YNOTE_CSTK", "你的CSTK值", ".note.youdao.com", "/"],
    ["YNOTE_SESS", "你的SESS值", ".note.youdao.com", "/"],
    ["YNOTE_LOGIN", "你的LOGIN值", ".note.youdao.com", "/"]
  ]
}
```

## 常见问题

### Q: 为什么cookies会过期？
A: 有道云笔记的cookies有时效性，通常几天到几周后会失效。需要定期重新获取。

### Q: 获取cookies后还是提示认证失败？
A: 请检查：
1. cookies.json 文件格式是否正确（必须是有效的JSON）
2. 是否包含了所有必需的cookie（YNOTE_CSTK、YNOTE_SESS、YNOTE_LOGIN）
3. 浏览器中是否真的处于登录状态
4. 网络连接是否正常

### Q: 如何验证cookies是否有效？
A: 重新启动GUI，如果能正常显示文件列表，说明cookies有效。

## 安全提示

⚠️ **cookies.json 包含你的登录凭证，请妥善保管，不要分享给他人！**

