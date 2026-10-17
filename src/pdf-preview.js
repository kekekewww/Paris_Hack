import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.mjs?url';

GlobalWorkerOptions.workerSrc=workerUrl;

// 僅在本機記憶體解析與繪製；不執行PDF中的腳本、附件或表單動作。
export async function inspectPdf(file){
  const task=getDocument({data:new Uint8Array(await file.arrayBuffer()),isEvalSupported:false,enableXfa:false,cMapUrl:'/pdfjs/cmaps/',cMapPacked:true,standardFontDataUrl:'/pdfjs/standard_fonts/',wasmUrl:'/pdfjs/wasm/',iccUrl:'/pdfjs/iccs/',useSystemFonts:true});
  let pdf;
  try{pdf=await task.promise}catch(error){await task.destroy();throw new Error(error?.name==='PasswordException'?'PDF有密碼保護，請改用可供檢查的無密碼副本。':'無法讀取此PDF，請確認檔案完整且未損毀。')}
  if(pdf.numPages>10||pdf.numPages<1){await task.destroy();throw new Error('PDF不可超過10頁，請拆分後重新選擇。')}
  let renderTask=null;
  return {
    pageCount:pdf.numPages,
    async render(canvas,pageNumber=1){
      renderTask?.cancel();
      const page=await pdf.getPage(pageNumber);
      if(!canvas.isConnected)return;
      const natural=page.getViewport({scale:1});
      const scale=Math.min(1.5,1000/natural.width,1600/natural.height);
      const viewport=page.getViewport({scale});
      canvas.width=Math.ceil(viewport.width);canvas.height=Math.ceil(viewport.height);
      renderTask=page.render({canvasContext:canvas.getContext('2d'),viewport});
      await renderTask.promise;page.cleanup();
    },
    async destroy(){renderTask?.cancel();await task.destroy()},
  };
}
