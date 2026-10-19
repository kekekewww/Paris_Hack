import {test,expect} from '@playwright/test';

function pdfFile(pages){
  const bodies=['<< /Type /Catalog /Pages 2 0 R >>',`<< /Type /Pages /Count ${pages} /Kids [${Array.from({length:pages},(_,i)=>`${i*2+3} 0 R`).join(' ')}] >>`];
  for(let i=0;i<pages;i++){
    bodies.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 ${pages*2+3} 0 R >> >> /Contents ${i*2+4} 0 R >>`);
    const text=`BT /F1 20 Tf 50 750 Td (Synthetic Claim Page ${i+1}) Tj ET`;
    bodies.push(`<< /Length ${Buffer.byteLength(text)} >>\nstream\n${text}\nendstream`);
  }
  bodies.push('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>');
  let pdf='%PDF-1.4\n';const offsets=[0];
  bodies.forEach((body,i)=>{offsets.push(Buffer.byteLength(pdf));pdf+=`${i+1} 0 obj\n${body}\nendobj\n`});
  const xref=Buffer.byteLength(pdf);pdf+=`xref\n0 ${offsets.length}\n0000000000 65535 f \n${offsets.slice(1).map(o=>`${String(o).padStart(10,'0')} 00000 n \n`).join('')}trailer\n<< /Size ${offsets.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return Buffer.from(pdf);
}
async function openUpload(page){
  await page.goto('/?service=mock#search');
  await page.getByRole('button',{name:'醫療門診',exact:true}).click();
  await page.getByRole('button',{name:'建立文件清單',exact:true}).click();
  await page.locator('article').first().getByRole('button',{name:'上傳與檢查',exact:true}).click();
  return page.getByRole('dialog');
}
test('PDF前端實際計頁拒絕11頁，且可換成有效文件恢復',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));const dialog=await openUpload(page);
  await dialog.getByLabel('選擇文件',{exact:true}).setInputFiles({name:'eleven.pdf',mimeType:'application/pdf',buffer:pdfFile(11)});
  await expect(dialog.locator('#upload-error')).toContainText('PDF不可超過10頁');
  await expect(dialog.locator('#analysis-results')).toBeEmpty();
  await expect(dialog.getByRole('button',{name:'開始分析',exact:true})).toBeDisabled();
  await dialog.getByLabel('選擇文件',{exact:true}).setInputFiles({name:'two.pdf',mimeType:'application/pdf',buffer:pdfFile(2)});
  await expect(dialog.locator('#file-info')).toContainText('2 頁');
  await expect(dialog.getByRole('button',{name:'開始分析',exact:true})).toBeEnabled();
  await dialog.getByRole('button',{name:'開始分析',exact:true}).click();
  await expect(dialog.locator('#pdf-canvas')).toBeVisible();
  await dialog.getByLabel('預覽頁碼').selectOption('2');
  await expect(dialog.getByLabel('預覽頁碼')).toHaveValue('2');
  await expect(dialog.locator('#pdf-canvas')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  const article=page.locator('article[data-document-id]').first();
  await expect(article.getByRole('button',{name:'上傳與檢查',exact:true})).toHaveCount(0);
  const result=article.getByRole('button',{name:'查看檢查結果',exact:true});
  await expect(result).toBeFocused();
  await result.press('Enter');
  await expect(page.getByRole('dialog').locator('#analysis-results')).toContainText('Mock');
  await expect(page.getByRole('dialog').getByLabel('選擇文件',{exact:true})).toBeEnabled();
  await page.keyboard.press('Escape');
  await expect(result).toBeFocused();
  expect(errors).toEqual([]);
});
test('損毀PDF不會被當成可分析文件',async({page})=>{
  const dialog=await openUpload(page);
  await dialog.getByLabel('選擇文件',{exact:true}).setInputFiles({name:'broken.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4 broken')});
  await expect(dialog.locator('#upload-error')).toContainText('無法讀取此PDF');
  await expect(dialog.locator('#analysis-results')).toBeEmpty();
  await expect(dialog.getByRole('button',{name:'開始分析',exact:true})).toBeDisabled();
  await dialog.getByLabel('選擇文件',{exact:true}).setInputFiles({name:'recovered.pdf',mimeType:'application/pdf',buffer:pdfFile(1)});
  await expect(dialog.locator('#file-info')).toContainText('1 頁');
  await expect(dialog.locator('#upload-error')).toBeEmpty();
  await expect(dialog.getByRole('button',{name:'開始分析',exact:true})).toBeEnabled();
  await dialog.getByRole('button',{name:'開始分析',exact:true}).click();
  await expect(dialog.locator('#pdf-canvas')).toBeVisible();
});
