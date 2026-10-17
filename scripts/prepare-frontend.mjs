import fs from 'node:fs';
const original = fs.readFileSync('法國巴黎人壽_理賠申請系統.html','utf8');
fs.mkdirSync('assets',{recursive:true});
const logo = original.match(/src="data:image\/png;base64,([^"]+)"/)[1];
fs.writeFileSync('assets/brand.png',Buffer.from(logo,'base64'));
let home = original.slice(original.indexOf('  <div id="viewTriage"'), original.indexOf('  <!-- VIEW 2:'));
home = home.slice(0,home.lastIndexOf('  <!-- ========================================================================= -->'));
home = home.replace(/src="data:image\/png;base64,[^"]+"/g,'src="/assets/brand.png"');
home = home.replace(/onclick="switchView\('([^']+)'\)"/g,'data-route="$1"');
home = home.replace('<div class="flex items-center gap-3">','<div class="home-nav"><span class="mode-label">展示原型 · Mock</span><a href="https://life.cardif.com.tw/zh/a314" target="_blank" rel="noopener noreferrer">官方理賠資訊 ↗</a><button data-action="resume" class="text-link" id="homeResume" hidden>繼續準備</button>');
home = home.replace('選擇你想要的協助方式','選擇你想要的協助方式，一起整理送件前的每一步。');
home = home.replace('溫馨提醒：AI 助手僅協助您準備理賠資料與檢查清單，最終理賠結果與給付項目仍須依保單條款及保險公司審查為準。','展示原型，請只使用虛構資料。AI 與文件初步檢查僅協助準備，不代表理賠核准；給付仍依保單及正式審核。');
const deco = original.slice(original.indexOf('  <!-- Background Decorative'),original.indexOf('  <!-- JAVASCRIPT:'));
fs.writeFileSync('index.html',`<!doctype html>
<html lang="zh-TW"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#00875A"><meta name="description" content="理賠文件準備助手：官方資料、文件清單與初步檢查。黑客松展示原型。"><link rel="icon" href="data:,"><title>理賠文件準備助手</title><link rel="stylesheet" href="/src/styles/generated.css"><link rel="stylesheet" href="/src/styles/app.css"></head>
<body><a href="#main-content" class="skip-link">跳至主要內容</a>${home}<div id="app" hidden></div><div id="toast" role="status" aria-live="polite"></div><div id="dialog-root"></div>${deco}<script type="module" src="/src/app.js"></script></body></html>`);
