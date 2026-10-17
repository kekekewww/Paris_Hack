import config from './playwright.config.js';
export default {...config,testMatch:'pdf.spec.js',projects:config.projects.filter(p=>p.name==='desktop-1440'),reporter:[['list']]};
