import {test,expect} from '@playwright/test';

// 全程使用公開介面、虛構圖片與Mock，不覆寫案件資料或呼叫外部模型。
const syntheticPng=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a1ioAAAAASUVORK5CYII=','base64');
const filename='synthetic-feedback.png';
const upload=(buffer=syntheticPng)=>({name:filename,mimeType:'image/png',buffer});

async function noOverflow(page){
  const dimensions=await page.evaluate(()=>({width:document.documentElement.clientWidth,content:document.documentElement.scrollWidth,dialog:(()=>{const d=document.querySelector('dialog[open]');return d?{width:d.clientWidth,content:d.scrollWidth}:null})()}));
  expect(dimensions.content,'主畫面不應橫向溢出').toBeLessThanOrEqual(dimensions.width+1);
  if(dimensions.dialog)expect(dimensions.dialog.content,'檢查視窗不應橫向溢出').toBeLessThanOrEqual(dimensions.dialog.width+1);
}

async function startDirect(page,{completeConditions=false}={}){
  await page.goto('/?service=mock#triage');
  await page.getByRole('button',{name:'選擇理賠類型',exact:true}).click();
  await page.getByRole('button',{name:'住院醫療',exact:true}).click();
  await page.getByLabel('事故原因',{exact:true}).selectOption('illness');
  await page.getByLabel('是否接受手術',{exact:true}).selectOption('no');
  await page.getByLabel('收據用途',{exact:true}).selectOption('actual');
  await page.getByText('更多準備條件',{exact:true}).click();
  await page.getByLabel('預計給付方式',{exact:true}).selectOption('remittance');
  if(completeConditions){
    await page.getByLabel('是否首次申請癌症／重大疾病',{exact:true}).selectOption('no');
    await page.getByLabel('診斷書是否載明手術部位及方式',{exact:true}).selectOption('no');
  }
  await page.getByRole('button',{name:'建立文件清單',exact:true}).click();
  await expect(page.getByRole('heading',{name:'文件準備工作區',exact:true})).toBeVisible();
  await noOverflow(page);
}

async function openApplication(page){
  const card=page.locator('article[data-document-id="application"]');
  await card.getByRole('button',{name:/^(上傳與檢查|查看檢查結果)$/}).click();
  const dialog=page.getByRole('dialog');
  await expect(dialog.getByRole('heading',{name:'文件初步檢查',exact:true})).toBeVisible();
  return dialog;
}

async function analyzeMissing(dialog){
  await dialog.getByLabel('選擇文件',{exact:true}).setInputFiles(upload());
  await dialog.getByLabel('模擬分析情境',{exact:true}).selectOption('missing');
  await dialog.getByRole('button',{name:'開始分析',exact:true}).click();
  await expect(dialog.getByRole('heading',{name:'分析結果',exact:true})).toBeVisible();
  await expect(dialog.locator('.finding').first()).toBeVisible();
}

test.beforeEach(async({page})=>{
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  page.on('console',message=>{if(message.type()==='error')errors.push(message.text())});
  page.__feedbackErrors=errors;
});
test.afterEach(async({page})=>{expect(page.__feedbackErrors,'不得有未處理的JavaScript或console錯誤').toEqual([])});

test('人工備妥、摘要、同分頁原檔重開與重整後指紋核對',async({page},testInfo)=>{
  test.setTimeout(90_000);
  await startDirect(page);
  const progress=page.getByRole('progressbar',{name:'文件準備進度'});
  const initialReady=Number(await progress.getAttribute('aria-valuenow'));
  let dialog=await openApplication(page);
  await analyzeMissing(dialog);
  const findings=await dialog.locator('.finding').count();
  const complete=dialog.getByRole('button',{name:'我已人工核對並備妥',exact:true});
  await expect(complete).toBeDisabled();
  while(await dialog.getByRole('button',{name:'我已人工確認',exact:true}).count()){
    const pending=dialog.getByRole('button',{name:'我已人工確認',exact:true});
    const count=await pending.count();
    await pending.first().click();
    await expect(pending).toHaveCount(count-1);
  }
  await expect(complete).toBeEnabled();
  await complete.click();
  await expect(dialog.getByText('✓ 已人工核對並備妥；原辨識提醒保留。',{exact:true})).toBeVisible();
  await expect(dialog.locator('.finding')).toHaveCount(findings);
  await expect(dialog.getByText(/信心.*\d+%|信心.*\d+％/)).toHaveCount(0);
  await noOverflow(page);
  await page.screenshot({path:testInfo.outputPath('manual-ready.png'),fullPage:true});
  await dialog.getByRole('button',{name:'關閉文件檢查',exact:true}).click();
  await expect(progress).toHaveAttribute('aria-valuenow',String(initialReady+1));
  await expect(page.locator('[data-document-id="application"] .status-ready')).toContainText('已人工核對並備妥');

  dialog=await openApplication(page);
  const actualPreview=dialog.getByRole('img',{name:'本次上傳文件預覽',exact:true});
  await expect(actualPreview).toBeVisible();
  await expect(actualPreview).toHaveAttribute('src',/^blob:/);
  expect(await actualPreview.evaluate(image=>image.complete&&image.naturalWidth>0)).toBe(true);
  await expect(dialog.locator('#file-info')).toContainText(filename);
  await dialog.getByRole('button',{name:'關閉文件檢查',exact:true}).click();
  await page.getByRole('button',{name:'查看準備摘要',exact:true}).click();
  const summaryRow=page.locator('tr').filter({hasText:'保險金申請書'});
  await expect(summaryRow).toContainText('已人工核對並備妥');
  await expect(summaryRow).toContainText('原辨識結果保留');
  await page.getByRole('button',{name:'返回工作區',exact:true}).click();

  dialog=await openApplication(page);
  await expect(dialog.getByRole('img',{name:'本次上傳文件預覽',exact:true})).toBeVisible();
  await expect(dialog.getByLabel('選擇文件',{exact:true})).toHaveJSProperty('required',false);
  await expect(dialog.getByRole('button',{name:'開始分析',exact:true})).toBeEnabled();
  await dialog.getByRole('button',{name:'開始分析',exact:true}).click();
  await expect(dialog.getByRole('button',{name:'我已人工核對並備妥',exact:true})).toBeDisabled();
  await expect(dialog.locator('.finding.confirmed')).toHaveCount(0);
  await expect(dialog.getByRole('button',{name:'我已人工確認',exact:true})).toHaveCount(findings);
  await dialog.getByRole('button',{name:'關閉文件檢查',exact:true}).click();
  await expect(progress).toHaveAttribute('aria-valuenow',String(initialReady));

  await page.reload();
  await expect(page.getByRole('heading',{name:'文件準備工作區',exact:true})).toBeVisible();
  dialog=await openApplication(page);
  await expect(dialog.getByText('請重新選取原始文件',{exact:true})).toBeVisible();
  await expect(dialog.locator('.marker')).toHaveCount(0);
  await expect(dialog.getByRole('img',{name:'本次上傳文件預覽',exact:true})).toHaveCount(0);
  await dialog.getByLabel('選擇文件',{exact:true}).setInputFiles(upload());
  await expect(dialog.getByRole('img',{name:'本次上傳文件預覽',exact:true})).toBeVisible();
  await expect(dialog.locator('.finding')).toHaveCount(findings);
  await dialog.getByRole('button',{name:'關閉文件檢查',exact:true}).click();

  await page.reload();
  dialog=await openApplication(page);
  const differentBytes=Buffer.from(syntheticPng);differentBytes[differentBytes.length-1]^=1;
  await dialog.getByLabel('選擇文件',{exact:true}).setInputFiles(upload(differentBytes));
  await expect(dialog.locator('#upload-error')).toContainText(/不一致|不同|重新分析/);
  await expect(dialog.locator('.marker')).toHaveCount(0);
  await expect(dialog.locator('#analysis-results .finding')).toHaveCount(0);
  await expect(dialog.getByRole('button',{name:'開始分析',exact:true})).toBeEnabled();
  await noOverflow(page);
  await page.screenshot({path:testInfo.outputPath('fingerprint-mismatch.png'),fullPage:true});
});

test('清單篩選、官方分類搜尋及常見問題保留可追溯來源',async({page},testInfo)=>{
  test.setTimeout(60_000);
  await startDirect(page);
  const filters=page.getByRole('group',{name:'篩選文件'});
  await filters.getByRole('button',{name:'已完成',exact:true}).click();
  await expect(filters.getByRole('button',{name:'已完成',exact:true})).toHaveAttribute('aria-pressed','true');
  await expect(page.locator('#document-list .status-pending')).toHaveCount(0);
  await filters.getByRole('button',{name:'待準備',exact:true}).click();
  await expect(page.locator('#document-list [data-document-id="application"]')).toBeVisible();
  await filters.getByRole('button',{name:'待確認',exact:true}).click();
  await expect(page.locator('#document-list .doc-card').first()).toContainText(/適用條件待確認|需要補充或人工確認/);
  await filters.getByRole('button',{name:'全部',exact:true}).click();
  await page.getByLabel('搜尋清單文件',{exact:true}).fill('保險金申請書');
  await expect(page.locator('#document-list .doc-card')).toHaveCount(1);
  const application=page.locator('#document-list [data-document-id="application"]');
  await expect(application.getByRole('heading',{name:'保險金申請書',exact:true})).toBeVisible();
  await application.locator('details.document-details > summary').click();
  const links=await application.getByRole('link').evaluateAll(elements=>elements.map(element=>element.href));
  expect(links.length,'文件卡應保留空白表單、填寫範例與官方依據').toBeGreaterThan(1);
  expect(new Set(links).size,'同一文件的官方完整網址應去重並保留用途標示').toBe(links.length);
  await page.getByRole('navigation',{name:'工作區導覽',exact:true}).getByRole('link',{name:'官方文件庫',exact:true}).click();
  await expect(page.getByRole('heading',{name:'官方文件庫',exact:true})).toBeVisible();
  const results=page.locator('.library-document');
  await expect(results.first()).toBeVisible();
  await page.getByLabel('文件分類',{exact:true}).selectOption('claims');
  await page.getByLabel('搜尋文件或商品代碼',{exact:true}).fill('申請書');
  await page.getByRole('button',{name:'查詢',exact:true}).click();
  await expect.poll(async()=>{
    const cards=await results.allTextContents();
    return cards.length>0&&cards.every(text=>text.includes('申請書')&&text.includes('理賠表單與須知'));
  },{message:'查詢完成後只顯示分類與關鍵字均符合的官方文件'}).toBe(true);
  for(const result of await results.all())await expect(result.locator('.badge')).toContainText('理賠表單與須知');
  for(const link of await results.getByRole('link',{name:/開啟官方文件/}).all())await expect(link).toHaveAttribute('href',/^https:\/\/life\.cardif\.com\.tw\//);
  await noOverflow(page);
  await page.screenshot({path:testInfo.outputPath('library-search.png'),fullPage:true});
  await page.getByLabel('搜尋文件或商品代碼',{exact:true}).fill('不存在的合成代碼ZZZZ9999');
  await page.getByRole('button',{name:'查詢',exact:true}).click();
  await expect(page.getByText('找不到符合文件，請調整搜尋或分類。',{exact:true})).toBeVisible();
  await page.getByRole('navigation',{name:'資訊導覽',exact:true}).getByRole('link',{name:'常見問題',exact:true}).click();
  await expect(page.getByRole('heading',{name:'常見問題',exact:true})).toBeVisible();
  const faq=page.locator('.faq-list details').first();
  await expect(faq).toBeVisible();
  await faq.locator('summary').click();
  await expect(faq.getByRole('link').first()).toHaveAttribute('href',/^https:\/\/life\.cardif\.com\.tw\//);
  await noOverflow(page);
  await page.screenshot({path:testInfo.outputPath('faq.png'),fullPage:true});
});

test('工作區更正須核對差異後確認，短答與取消不變更案件',async({page},testInfo)=>{
  test.setTimeout(60_000);
  await startDirect(page,{completeConditions:true});
  const surgery=page.locator('[data-document-id="surgery"]');
  await expect(surgery.locator('.applicability')).toHaveText('已確認不適用');
  await page.getByRole('button',{name:'開啟助手',exact:true}).click();
  const assistant=page.getByRole('complementary',{name:'理賠準備助手',exact:true});
  const send=async message=>{
    await assistant.getByLabel('詢問文件準備問題',{exact:true}).fill(message);
    await assistant.getByRole('button',{name:'送出問題',exact:true}).click();
    await expect(page.locator('#busy-status')).toBeEmpty();
  };
  await send('更正，我有接受手術');
  const proposal=assistant.getByRole('region',{name:'案件變更提案',exact:true});
  await expect(proposal).toBeVisible();
  await expect(proposal.locator('dl')).toContainText('手術');
  await expect(proposal.locator('dd').first()).toContainText('沒有');
  await expect(proposal.locator('dd').first()).toContainText('有');
  await expect(surgery.locator('.applicability')).toHaveText('已確認不適用');
  await send('是');
  await expect(proposal).toBeVisible();
  await expect(surgery.locator('.applicability')).toHaveText('已確認不適用');
  await proposal.getByRole('button',{name:'取消變更',exact:true}).click();
  await expect(proposal).toHaveCount(0);
  await expect(surgery.locator('.applicability')).toHaveText('已確認不適用');
  await send('更正，我有接受手術');
  await expect(proposal).toBeVisible();
  await proposal.getByRole('button',{name:'確認更新',exact:true}).click();
  await expect(proposal).toHaveCount(0);
  await expect(surgery.locator('.applicability')).toHaveText('確認需要');
  await expect(surgery).toContainText('尚未準備');
  await noOverflow(page);
  await page.screenshot({path:testInfo.outputPath('proposal-confirmed.png'),fullPage:true});
  await page.getByRole('button',{name:'查看準備摘要',exact:true}).click();
  const row=page.locator('tr').filter({hasText:'手術證明文件'});
  await expect(row).toContainText('尚未準備');
  await expect(row).not.toContainText('已確認不適用');
  await page.getByRole('button',{name:'返回工作區',exact:true}).click();
  await page.reload();
  await expect(page.locator('[data-document-id="surgery"] .applicability')).toHaveText('確認需要');
});
