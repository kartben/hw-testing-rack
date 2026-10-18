// Bay cameras: the Arducam Mega pod under the ceiling, its two LED light boxes, and the preview.
// Geometry comes from rack.json › cameras (tools/webscene.py › CAMERA_LENS / CAMERA_RIG), in the frame
// of the row above (millimetres, Z up, the ceiling at z = 0); the lens looks straight down (-Z).
import * as THREE from 'three';
import { RectAreaLightUniformsLib } from 'three/addons/lights/RectAreaLightUniformsLib.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

RectAreaLightUniformsLib.init();

const deg = THREE.MathUtils.degToRad;
const LED_WHITE = new THREE.Color(1.0, 0.96, 0.9);   // ~5500 K behind white PETG

// Printed parts get the viewer's layer-line shader; it needs each vertex's build-plate normal.
function printed(geo, up = [0, 0, 1]) {
  geo.setAttribute('printUp', new THREE.Float32BufferAttribute(
    new Float32Array(geo.attributes.position.count * 3).map((_, i) => up[i % 3]), 3));
  return geo;
}
function boxAt(w, l, h, mat, x, y, z) {          // centred in x/y, z = its bottom
  const m = new THREE.Mesh(printed(new THREE.BoxGeometry(w, l, h)), mat);
  m.position.set(x, y, z + h / 2);
  return m;
}

// The diffuser's glow: three LEDs 8 mm behind 1 mm of white PETG spread into soft overlapping spots,
// a little brighter where the box's white walls send light back in; drawn once into a texture.
function diffuserTexture(size, leds, gap) {
  const [w, l] = size;
  const c = document.createElement('canvas');
  c.width = 64; c.height = Math.round(64 * l / w);
  const g = c.getContext('2d');
  const img = g.createImageData(c.width, c.height);
  const sigma = gap * 0.75;
  let max = 0;
  const vals = new Float32Array(c.width * c.height);
  for (let j = 0; j < c.height; j++) {
    for (let i = 0; i < c.width; i++) {
      const x = ((i + 0.5) / c.width - 0.5) * w, y = ((j + 0.5) / c.height - 0.5) * l;
      let v = 0;
      for (let k = 0; k < leds; k++) {
        const ly = ((k + 0.5) / leds - 0.5) * l;
        const d2 = x * x + (y - ly) * (y - ly);
        v += Math.exp(-d2 / (2 * sigma * sigma)) + 0.35 / (1 + d2 / (gap * gap * 4));
      }
      const edge = Math.min(w / 2 - Math.abs(x), l / 2 - Math.abs(y));
      v *= 0.82 + 0.18 * Math.exp(-edge / 2.5);     // the walls' bounce at the rim
      vals[j * c.width + i] = v;
      max = Math.max(max, v);
    }
  }
  for (let p = 0; p < vals.length; p++) {
    const v = Math.pow(vals[p] / max, 0.9) * 255;
    img.data.set([v, v * 0.97, v * 0.92, 255], p * 4);
  }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// Glare round a lit diffuser (what an eye or a lens adds round a bright source): a soft rim in the
// diffuser's plane, added on top, facing down.
function glareTexture(size, margin) {
  const [w, l] = size;
  const W = w + 2 * margin, L = l + 2 * margin;
  const c = document.createElement('canvas');
  c.width = 96; c.height = Math.round(96 * L / W);
  const g = c.getContext('2d');
  const img = g.createImageData(c.width, c.height);
  for (let j = 0; j < c.height; j++) for (let i = 0; i < c.width; i++) {
    const x = Math.abs(((i + 0.5) / c.width - 0.5) * W) - w / 2, y = Math.abs(((j + 0.5) / c.height - 0.5) * L) - l / 2;
    const d = Math.hypot(Math.max(x, 0), Math.max(y, 0));
    const a = 0.55 * Math.exp(-(d * d) / (2 * 2.6 * 2.6)) + 0.18 * Math.exp(-d / 5.5);
    img.data.set([255, 246, 232, Math.round(255 * Math.min(1, a))], (j * c.width + i) * 4);
  }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// ------------------------------------------------------------------ the pod
export function makeCameraRig(cam, M) {
  const g = new THREE.Group();
  const [lx, ly, lz] = cam.lens;
  g.position.set(lx, ly, 0);
  const drop = -lz;
  const [pw, pl, pt] = cam.plate;
  // plate and its arm to the ceiling's insert square (the pod is cantilevered off the four inserts)
  const [mx, my, mp] = cam.mount;
  const hull = (pts) => {                           // convex hull, Andrew's monotone chain
    pts = pts.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
    const lo = [], up = [];
    for (const p of pts) { while (lo.length >= 2 && cross(lo.at(-2), lo.at(-1), p) <= 0) lo.pop(); lo.push(p); }
    for (const p of pts.reverse()) { while (up.length >= 2 && cross(up.at(-2), up.at(-1), p) <= 0) up.pop(); up.push(p); }
    return lo.slice(0, -1).concat(up.slice(0, -1));
  };
  const s = mp / 2 + 6;
  const outline = hull([[-pw / 2, -pl / 2], [pw / 2, -pl / 2], [pw / 2, pl / 2], [-pw / 2, pl / 2],
    [mx - s, my - s], [mx + s, my - s], [mx + s, my + s], [mx - s, my + s]]);
  const shape = new THREE.Shape(outline.map(([x, y]) => new THREE.Vector2(x, y)));
  const plateGeo = new THREE.ExtrudeGeometry(shape, { depth: pt, bevelEnabled: true, bevelThickness: 0.6, bevelSize: 0.6, bevelSegments: 2 });
  plateGeo.translate(0, 0, -pt);
  const plate = new THREE.Mesh(printed(plateGeo), M.cameras);
  g.add(plate);
  for (const dx of [-mp / 2, mp / 2]) for (const dy of [-mp / 2, mp / 2]) {     // M3 heads in their recesses
    const h = new THREE.Mesh(new THREE.CylinderGeometry(2.7, 2.7, 1.2, 20), M.silver);
    h.rotation.x = Math.PI / 2;
    h.position.set(mx + dx, my + dy, -pt + 0.5);
    g.add(h);
  }
  // the Mega: PCB on four standoffs, the M12 holder and the lens below it
  const [bw, bl, bt] = cam.board;
  const zb = -pt - 3;                                 // PCB top face
  g.add(boxAt(bw, bl, bt, M.megaPcb, 0, 0, zb - bt));
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) g.add(boxAt(3.4, 3.4, 3, M.cameras, sx * (bw / 2 - 3), sy * (bl / 2 - 3), zb));
  const zh = zb - bt;                                 // underside of the PCB
  g.add(boxAt(15, 15, 9, M.blackPlastic, 0, 0, zh - 9));
  const barrel = new THREE.Mesh(new THREE.CylinderGeometry(6.2, 6.2, drop + zh + 9 - 2.5, 36), M.lensBody);
  barrel.rotation.x = Math.PI / 2;
  barrel.position.set(0, 0, (zh - 9 - drop + 2.5) / 2);
  const ring = new THREE.Mesh(new THREE.CylinderGeometry(7.2, 7.2, 2.5, 36), M.lensBody);
  ring.rotation.x = Math.PI / 2;
  ring.position.set(0, 0, -drop + 1.25);
  const glass = new THREE.Mesh(new THREE.CircleGeometry(4.6, 36), M.glass);
  glass.rotation.x = Math.PI;                        // facing down
  glass.position.set(0, 0, -drop - 0.01);
  g.add(barrel, ring, glass);
  // light boxes: LED strip on the plate, white walls (the baffle towards the lens), the diffuser
  const lights = [];
  for (const L of cam.lights) {
    const [ax, ay] = L.at, [w, l] = L.size;
    const t = 1.2, zDiff = -pt - L.gap - L.diffuser;
    for (const [x, y, ww, ll] of [[ax - w / 2 - t / 2, ay, t, l + 2 * t], [ax + w / 2 + t / 2, ay, t, l + 2 * t],
      [ax, ay - l / 2 - t / 2, w, t], [ax, ay + l / 2 + t / 2, w, t]]) {
      g.add(boxAt(ww, ll, L.gap + L.diffuser, M.cameras, x, y, zDiff));
    }
    g.add(boxAt(8, l - 2, 0.3, M.ledStrip, ax, ay, -pt - 0.3));
    const ledMat = new THREE.MeshStandardMaterial({ color: 0xf6f3e8, emissive: LED_WHITE, emissiveIntensity: 0, roughness: 0.3 });
    for (let k = 0; k < L.leds; k++) {
      const yk = ay + ((k + 0.5) / L.leds - 0.5) * l;
      g.add(boxAt(5, 5, 1.6, ledMat, ax, yk, -pt - 1.9));
    }
    const glow = diffuserTexture(L.size, L.leds, L.gap);
    const diffMat = new THREE.MeshStandardMaterial({ color: 0xf1efe8, roughness: 0.62, emissive: LED_WHITE, emissiveMap: glow, emissiveIntensity: 0 });
    const diff = boxAt(w, l, L.diffuser, diffMat, ax, ay, zDiff);
    g.add(diff);
    const glareMat = new THREE.MeshBasicMaterial({ map: glareTexture(L.size, 12), transparent: true, opacity: 0,
      blending: THREE.AdditiveBlending, depthWrite: false });
    const glare = new THREE.Mesh(new THREE.PlaneGeometry(w + 24, l + 24), glareMat);
    glare.rotation.x = Math.PI;                    // faces down, like the diffuser
    glare.position.set(ax, ay, zDiff - 0.2);
    glare.renderOrder = 2;
    g.add(glare);
    // the light: an area light the size of the diffuser (soft, no cone), plus a wide spot from the same
    // spot for the shadows an area light cannot cast in three.js
    const area = new THREE.RectAreaLight(LED_WHITE, 0, w, l);
    area.position.set(ax, ay, zDiff - 0.05);       // emits along its -Z: down
    const spot = new THREE.SpotLight(LED_WHITE, 0, 0, deg(80), 1, 2);
    spot.position.set(ax, ay, zDiff - 0.5);
    spot.target.position.set(ax, ay, zDiff - 200);
    spot.castShadow = true;
    spot.shadow.mapSize.set(512, 512);
    spot.shadow.camera.near = 2;
    spot.shadow.camera.far = 180;
    spot.shadow.bias = -0.0006;
    spot.shadow.normalBias = 0.4;
    spot.shadow.autoUpdate = false;
    g.add(area, spot, spot.target);
    lights.push({ area, spot, diffMat, ledMat, glareMat });
  }
  // the lens' frame: x along the bay's depth (the sensor's long side), y towards the bay's left, looking down
  const lens = new THREE.Object3D();
  lens.position.set(0, 0, -drop - 0.3);
  lens.matrixAutoUpdate = true;
  lens.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(
    new THREE.Vector3(0, 1, 0), new THREE.Vector3(-1, 0, 0), new THREE.Vector3(0, 0, 1)));
  g.add(lens);
  g.traverse((o) => { o.userData.noShadow = true; });
  return { group: g, lens, lights, level: 0, target: 0, cam };
}

// Light level 0..1 (fades like a driver's soft start).  Sized from the parts: a 5 V 2835 strip runs its LEDs
// at ~0.1 W, ~10 lm each; 3 per box behind 1 mm of white PETG (~60 % through) give ~18 lm from 14 × 30 mm,
// a Lambertian luminance of ~14 000 cd/m², so ~1 100 lux on a board 10 cm below — some 2.5× what the
// room puts on surfaces in the open.  In the viewer's units (the sun is 2.2) that is ~10 on the board:
// half from the area lights (soft, wide, no cone), half from the spots, which cast the shadows.  The
// diffuser is far brighter than the board it lights; it is drawn just short of clipping, so its spread
// (three soft spots merging) still shows, with a glare rim round it.
export function setRigLight(rig, k) {
  if (k > 0 && !(rig.level > 0)) refreshRigShadows(rig);
  rig.level = k;
  for (const L of rig.lights) {
    L.area.intensity = 60 * k;
    L.spot.intensity = 28000 * k;
    L.diffMat.emissiveIntensity = 9 * k;            // bright enough to read white, dim enough to show the spread
    L.ledMat.emissiveIntensity = 40 * k;
    L.glareMat.opacity = 0.75 * k;
  }
}

// The shadow maps are drawn once, then again only when something in the bay moves (app.js › applyTransforms).
export function refreshRigShadows(rig) {
  for (const L of rig.lights) L.spot.shadow.needsUpdate = true;
}

// ------------------------------------------------------------------ the preview
const FS_VERT = /* glsl */`varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;

// Sensor + lens: equidistant fisheye from the rectilinear render, lateral chromatic aberration, softness
// growing towards the rim, vignetting, auto-exposure gain, an imperfect white balance, photon and read
// noise (worse when the gain is high), a cheap sensor's tone curve.
const SENSOR_FRAG = /* glsl */`
uniform sampler2D src; uniform vec2 srcSize; uniform float tanMax; uniform float thetaMax;
uniform float gain; uniform vec3 wb; uniform float frame;
varying vec2 vUv;
const vec2 A = vec2(0.8, 0.6);                 // 4:3, the corner at |q| = 1
float h12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
vec2 gauss(vec2 p) { float u1 = max(h12(p), 1e-6), u2 = h12(p + 17.17); return sqrt(-2.0 * log(u1)) * vec2(cos(6.2831853 * u2), sin(6.2831853 * u2)); }
vec2 srcUv(vec2 q) {
  float rd = max(length(q), 1e-6);
  float ru = tan(rd * thetaMax) / tanMax;      // equidistant (r = f·θ) → rectilinear (r = f·tan θ)
  return 0.5 + (q * (ru / rd)) / A * 0.5;
}
vec3 soft(vec2 q, float k) {                    // a small blur, wider at the rim
  vec2 d = vec2(k) / srcSize;
  vec2 c = srcUv(q);
  return (texture2D(src, c).rgb * 2.0 + texture2D(src, c + vec2(d.x, 0.0)).rgb + texture2D(src, c - vec2(d.x, 0.0)).rgb
          + texture2D(src, c + vec2(0.0, d.y)).rgb + texture2D(src, c - vec2(0.0, d.y)).rgb) / 6.0;
}
void main() {
  vec2 q = (vUv - 0.5) * 2.0 * A;
  float r2 = dot(q, q);
  float k = 0.7 + 3.2 * r2 * r2;
  vec3 col;
  col.r = soft(q * (1.0 + 0.010 * r2), k).r;
  col.g = soft(q, k).g;
  col.b = soft(q * (1.0 - 0.012 * r2), k).b;
  float vig = 1.0 - 0.42 * pow(r2, 1.15);
  vec3 lin = max(col, 0.0) * gain * wb * vig;
  float lum = dot(lin, vec3(0.299, 0.587, 0.114));
  vec2 px = floor(gl_FragCoord.xy);
  vec2 n1 = gauss(px + frame * 13.17), n2 = gauss(px * 1.37 + frame * 7.31 + 3.1);
  float sigma = sqrt(0.0025 * gain * gain * 0.06 + 0.0035 * max(lum, 0.0) * min(gain, 8.0));
  lin += sigma * (vec3(n1.x) + 0.55 * vec3(n1.y, n2.x * 0.8, n2.y));
  lin = max(lin - 0.006, 0.0);                  // black level, a little crushed
  vec3 tone = lin * 1.05 / (1.0 + 0.32 * lin);  // soft shoulder, then clip
  tone = mix(vec3(dot(tone, vec3(0.299, 0.587, 0.114))), tone, 0.86);
  gl_FragColor = vec4(pow(clamp(tone, 0.0, 1.0), vec3(1.0 / 2.2)), 1.0);
}`;

// The camera's ISP sharpening (a halo on edges), then YCbCr with 4:2:0 chroma, level-shifted to ±128.
const YCC_FRAG = /* glsl */`
uniform sampler2D src;
varying vec2 vUv;
vec3 ycc(vec3 c) { c *= 255.0; return vec3(0.299 * c.r + 0.587 * c.g + 0.114 * c.b,
  -0.168736 * c.r - 0.331264 * c.g + 0.5 * c.b, 0.5 * c.r - 0.418688 * c.g - 0.081312 * c.b); }
void main() {
  ivec2 p = ivec2(gl_FragCoord.xy);
  vec3 c = texelFetch(src, p, 0).rgb;
  vec3 n = texelFetch(src, p + ivec2(1, 0), 0).rgb + texelFetch(src, p - ivec2(1, 0), 0).rgb
         + texelFetch(src, p + ivec2(0, 1), 0).rgb + texelFetch(src, p - ivec2(0, 1), 0).rgb;
  float y = ycc(c).x + 0.55 * (ycc(c).x * 4.0 - ycc(n).x);
  ivec2 q = (p / 2) * 2;
  vec3 ch = ycc((texelFetch(src, q, 0).rgb + texelFetch(src, q + ivec2(1, 0), 0).rgb
               + texelFetch(src, q + ivec2(0, 1), 0).rgb + texelFetch(src, q + ivec2(1, 1), 0).rgb) * 0.25);
  gl_FragColor = vec4(y - 128.0, ch.y, ch.z, 1.0);
}`;

// Forward 8×8 DCT: every pixel computes the coefficient (u, v) of its block, for Y, Cb and Cr.
const DCT_FRAG = /* glsl */`
uniform sampler2D src; uniform float cosT[64];
void main() {
  ivec2 p = ivec2(gl_FragCoord.xy), b = (p / 8) * 8, uv = p - b;
  vec3 s = vec3(0.0);
  for (int j = 0; j < 8; j++) for (int i = 0; i < 8; i++)
    s += texelFetch(src, b + ivec2(i, j), 0).rgb * cosT[i * 8 + uv.x] * cosT[j * 8 + uv.y];
  float cu = uv.x == 0 ? 0.70710678 : 1.0, cv = uv.y == 0 ? 0.70710678 : 1.0;
  gl_FragColor = vec4(0.25 * cu * cv * s, 1.0);
}`;

// Quantise with the JPEG tables at the camera's quality, inverse DCT, back to RGB.
const IDCT_FRAG = /* glsl */`
uniform sampler2D src; uniform float cosT[64]; uniform float qY[64]; uniform float qC[64];
void main() {
  ivec2 p = ivec2(gl_FragCoord.xy), b = (p / 8) * 8, ij = p - b;
  int i = ij.x, j = ij.y;
  vec3 s = vec3(0.0);
  for (int v = 0; v < 8; v++) for (int u = 0; u < 8; u++) {
    vec3 F = texelFetch(src, b + ivec2(u, v), 0).rgb;
    float qy = qY[v * 8 + u], qc = qC[v * 8 + u];
    F = vec3(floor(F.x / qy + 0.5) * qy, floor(F.y / qc + 0.5) * qc, floor(F.z / qc + 0.5) * qc);
    float cu = u == 0 ? 0.70710678 : 1.0, cv = v == 0 ? 0.70710678 : 1.0;
    s += cu * cv * F * cosT[i * 8 + u] * cosT[j * 8 + v];
  }
  s *= 0.25;
  float y = s.x + 128.0, cb = s.y, cr = s.z;
  vec3 rgb = vec3(y + 1.402 * cr, y - 0.344136 * cb - 0.714136 * cr, y + 1.772 * cb) / 255.0;
  gl_FragColor = vec4(clamp(rgb, 0.0, 1.0), 1.0);
}`;

// Mean colour of the frame on a coarse grid, for the auto-exposure and the auto white balance.
const PROBE_FRAG = /* glsl */`
uniform sampler2D src; varying vec2 vUv; uniform vec2 cell;
void main() {
  vec3 s = vec3(0.0);
  for (int j = 0; j < 6; j++) for (int i = 0; i < 6; i++) s += texture2D(src, vUv + (vec2(i, j) - 2.5) / 6.0 * cell).rgb;
  gl_FragColor = vec4(s / 36.0, 1.0);
}`;

const Q_Y = [16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62,
  18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92, 49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99];
const Q_C = [17, 18, 24, 47, 99, 99, 99, 99, 18, 21, 26, 66, 99, 99, 99, 99, 24, 26, 56, 99, 99, 99, 99, 99, 47, 66, 99, 99, 99, 99, 99, 99,
  ...new Array(32).fill(99)];
const COS_T = Array.from({ length: 64 }, (_, k) => Math.cos(((2 * Math.floor(k / 8) + 1) * (k % 8) * Math.PI) / 16));

export class CameraPreview {
  constructor(renderer, canvas, { fps = 5, size = [640, 480], quality = 62, ambient = [] } = {}) {
    this.r = renderer;
    this.ctx = canvas.getContext('2d');
    this.fps = fps;
    this.size = size;
    this.ambient = ambient;                // [light, factor]: what the lens sees less of than the viewer (the sun)
    this.rig = null;
    this.last = -1e9;
    this.frame = 0;
    this.gain = 2;
    this.wb = new THREE.Vector3(1, 1, 1);
    const [w, h] = size;
    const sc = (200 - 2 * quality) / 100;           // libjpeg's table scaling for quality ≥ 50
    this.cam = new THREE.PerspectiveCamera(1, 4 / 3, 2.5, 3000);
    const fl = { type: THREE.FloatType, depthBuffer: false, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter };
    this.rtScene = new THREE.WebGLRenderTarget(1280, 960, { type: THREE.HalfFloatType, samples: 4 });
    this.rtSensor = new THREE.WebGLRenderTarget(w, h, { depthBuffer: false, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter });
    this.rtYcc = new THREE.WebGLRenderTarget(w, h, fl);
    this.rtDct = new THREE.WebGLRenderTarget(w, h, fl);
    this.rtOut = new THREE.WebGLRenderTarget(w, h, { depthBuffer: false });
    this.pixels = new Uint8ClampedArray(w * h * 4);   // the frame, read back into the panel's own canvas
    this.image = new ImageData(this.pixels, w, h);
    this.rtProbe = new THREE.WebGLRenderTarget(16, 12, fl);
    this.probeBuf = new Float32Array(16 * 12 * 4);
    const pass = (frag, uniforms) => new THREE.Mesh(new THREE.PlaneGeometry(2, 2),
      new THREE.ShaderMaterial({ vertexShader: FS_VERT, fragmentShader: frag, uniforms, depthTest: false, depthWrite: false }));
    this.sensor = pass(SENSOR_FRAG, { src: { value: this.rtScene.texture }, srcSize: { value: new THREE.Vector2(1280, 960) },
      tanMax: { value: 1 }, thetaMax: { value: 1 }, gain: { value: 1 }, wb: { value: this.wb }, frame: { value: 0 } });
    this.ycc = pass(YCC_FRAG, { src: { value: this.rtSensor.texture } });
    this.dct = pass(DCT_FRAG, { src: { value: this.rtYcc.texture }, cosT: { value: COS_T } });
    this.idct = pass(IDCT_FRAG, { src: { value: this.rtDct.texture }, cosT: { value: COS_T },
      qY: { value: Q_Y.map((q) => Math.max(1, Math.round(q * sc))) }, qC: { value: Q_C.map((q) => Math.max(1, Math.round(q * sc))) } });
    this.probe = pass(PROBE_FRAG, { src: { value: this.rtScene.texture }, cell: { value: new THREE.Vector2(1 / 16, 1 / 12) } });
    this.quadScene = new THREE.Scene();
    this.quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  }

  setRig(rig) {
    this.rig = rig;
    this.last = -1e9;
    if (!rig) return;
    const half = deg(rig.cam.fov / 2);
    this.sensor.material.uniforms.tanMax.value = Math.tan(half);
    this.sensor.material.uniforms.thetaMax.value = half;
    // the rectilinear render whose corner sits at the fisheye's half diagonal angle
    this.cam.fov = THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(half) * 0.6));
    this.cam.aspect = 4 / 3;
    this.cam.updateProjectionMatrix();
  }

  pass(mesh, target) {
    this.quadScene.add(mesh);
    this.r.setRenderTarget(target);
    this.r.render(this.quadScene, this.quadCam);
    this.quadScene.remove(mesh);
  }

  // Grab a frame at the camera's rate: render the bay from the lens, then run the sensor and the JPEG.
  update(scene, now, hide = []) {
    if (!this.rig || now - this.last < 1000 / this.fps) return false;
    const dt = Math.min(1, (now - this.last) / 1000);
    this.last = now;
    this.frame = (this.frame + 1) % 997;
    this.rig.lens.updateWorldMatrix(true, false);
    this.cam.matrixWorld.copy(this.rig.lens.matrixWorld);
    this.cam.matrixWorld.decompose(this.cam.position, this.cam.quaternion, this.cam.scale);
    this.cam.updateMatrixWorld(true);
    const saved = this.ambient.map(([l]) => l.intensity);
    this.ambient.forEach(([l, f]) => { l.intensity *= f; });
    const vis = hide.map((o) => o.visible);
    hide.forEach((o) => { o.visible = false; });
    const tm = this.r.toneMapping;
    this.r.toneMapping = THREE.NoToneMapping;
    this.r.setRenderTarget(this.rtScene);
    this.r.render(scene, this.cam);
    this.r.toneMapping = tm;
    hide.forEach((o, i) => { o.visible = vis[i]; });
    this.ambient.forEach(([l], i) => { l.intensity = saved[i]; });
    // auto-exposure and auto white balance, slow like the real thing
    this.pass(this.probe, this.rtProbe);
    this.r.readRenderTargetPixels(this.rtProbe, 0, 0, 16, 12, this.probeBuf);
    const m = [0, 0, 0];
    let wsum = 0;
    for (let j = 0; j < 12; j++) for (let i = 0; i < 16; i++) {
      const w = 1 - 0.6 * Math.hypot((i - 7.5) / 8, (j - 5.5) / 6) ** 2;
      for (let c = 0; c < 3; c++) m[c] += this.probeBuf[(j * 16 + i) * 4 + c] * w;
      wsum += w;
    }
    const lum = (0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2]) / wsum;
    const want = THREE.MathUtils.clamp(0.2 / Math.max(lum, 1e-5), 0.3, 28);
    const a = 1 - Math.exp(-dt / 0.45);
    this.gain += (want - this.gain) * a;
    const awb = [0, 1, 2].map((c) => Math.pow((lum * wsum) / Math.max(m[c], 1e-6), 0.45));   // grey-world, half-hearted
    const bias = [1.04, 1.0, 0.9];                      // the sensor's own cast: a touch green-yellow
    this.wb.set(...[0, 1, 2].map((c) => THREE.MathUtils.lerp(this.wb.getComponent(c), awb[c] * bias[c], a)));
    const u = this.sensor.material.uniforms;
    u.gain.value = this.gain;
    u.frame.value = this.frame;
    this.pass(this.sensor, this.rtSensor);
    this.pass(this.ycc, this.rtYcc);
    this.pass(this.dct, this.rtDct);
    this.pass(this.idct, this.rtOut);
    this.r.readRenderTargetPixels(this.rtOut, 0, 0, this.size[0], this.size[1], this.pixels);
    this.r.setRenderTarget(null);
    this.ctx.putImageData(this.image, 0, 0);       // bottom-up rows: the canvas is flipped in CSS
    return true;
  }
}
