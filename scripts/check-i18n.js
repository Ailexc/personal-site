// 临时校验：中英文案的键集合是否一致（一次性脚本）
global.window = {};
require("../public/assets/i18n.js");

const zh = Object.keys(window.I18N.zh);
const en = Object.keys(window.I18N.en);
const onlyEn = en.filter((k) => zh.indexOf(k) === -1);
const onlyZh = zh.filter((k) => en.indexOf(k) === -1);

console.log("zh 键数:", zh.length, " en 键数:", en.length);
console.log("仅 en 有:", onlyEn.length ? onlyEn.join(", ") : "无");
console.log("仅 zh 有:", onlyZh.length ? onlyZh.join(", ") : "无");
console.log("clicks.* 键数:", zh.filter((k) => k.indexOf("clicks.") === 0).length);
console.log("footer.note:", JSON.stringify(window.I18N.zh["footer.note"]));
