// 浏览器端一次性体检脚本：由 Node 注入到页面执行
// 步骤：强刷 → 打开最新任务的阅读器 → 等待渲染 → 返回各指标
(function () {
  return (async () => {
    location.href = "http://127.0.0.1:8000/?cb=" + Date.now();
  })();
})();
