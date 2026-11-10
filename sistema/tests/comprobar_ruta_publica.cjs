const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(process.argv[2], 'utf8');
const base = process.argv[3];
const solicitudes = [];
const nodos = {};
const nodo = id => nodos[id] ||= {
  classList: { add() {}, remove() {}, toggle() {} },
  addEventListener() {}, dataset: {}, style: {}, value: '',
};
const ctx = {
  URL, location: { href: base }, confirm: () => true,
  document: { getElementById: nodo, querySelectorAll: () => [] },
  window: { scrollTo() {} }, clearTimeout() {}, setTimeout() {},
  fetch: async ruta => {
    solicitudes.push(new URL(ruta, base).href);
    return { ok: true, json: async () => ({qwen: 'no_disponible'}) };
  },
};
vm.createContext(ctx);
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], ctx);
(async () => {
  await vm.runInContext("api('/api/generar', {method:'POST'})", ctx);
  vm.runInContext("R={sid:'sesion-prueba',momentos:[],destinos:{},curso:{nombre:'Prueba',id:'1'}}; G={control:{}}; pintar4({});", ctx);
  assert.equal(new URL(nodo('dl').href, base).href, base+'api/descargar/sesion-prueba');
  await nodo('fin').onclick();
  await nodo('inicio').onclick();
  for (const ruta of ['api/salud','api/generar','api/terminar/sesion-prueba']) {
    assert(solicitudes.includes(base+ruta), `La solicitud ${ruta} salió de la ruta pública: ${solicitudes}`);
  }
  assert.equal(new URL(ctx.location.href, base).href, base);
  console.log('Rutas HTTP, descarga y regreso al inicio correctos en '+base);
})().catch(e => { console.error(e.message); process.exitCode = 1; });
