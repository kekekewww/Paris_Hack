import {cp,copyFile,mkdir} from 'node:fs/promises';
await mkdir('public/assets',{recursive:true});
await copyFile('assets/brand.png','public/assets/brand.png');
for(const directory of ['cmaps','standard_fonts','wasm','iccs']){
  await cp(`node_modules/pdfjs-dist/${directory}`,`public/pdfjs/${directory}`,{recursive:true});
}
await copyFile('node_modules/pdfjs-dist/LICENSE','public/pdfjs/LICENSE');
