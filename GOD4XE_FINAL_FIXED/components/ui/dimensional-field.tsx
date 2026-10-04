import { useMemo, type CSSProperties } from "react";

type FocusRole = "background" | "button" | "visual";
type EffectMode = "light" | "dark";

type FocusTarget = {
  selector: string;
  role: FocusRole;
  fit?: "cover" | "contain-square" | "wide-wordmark" | "portrait-stage";
  preserveTransform?: boolean;
};

type EffectDefinition = {
  title: string;
  source: string;
  background: string;
  targets: readonly FocusTarget[];
  theme?: {
    nativeMode?: EffectMode;
    lightBackground: string;
    darkBackground: string;
    invertBackground?: boolean;
  };
  transformSource?: (source: string, mode: EffectMode) => string;
  hiddenTargets?: readonly string[];
  introWordmark?: {
    sceneSelector: string;
    text: string;
    fontSize: number;
    endTime: number;
    holdTime: number;
    logoSvg: string;
  };
};

export type DimensionalFieldProps = {
  mode?: EffectMode;
  hue?: number;
  saturation?: number;
  brightness?: number;
  className?: string;
  style?: CSSProperties;
};

const NEUFORM_ISOLATED_DEFAULTS = {
  mode: "dark",
  hue: 0,
  saturation: 1,
  brightness: 1,
} as const;

const dimensionalSource = `<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vanguard Labs — Dimensional Architecture</title>
    
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@200;300;400;500;600&display=swap" rel="stylesheet">
    
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://code.iconify.design/iconify-icon/1.0.7/iconify-icon.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/ScrollTrigger.min.js"></script>
</head>
<body class="bg-[#050505] text-gray-100 font-sans antialiased overflow-hidden selection:bg-cyan-500/20 selection:text-cyan-100" style="font-family: 'Inter', sans-serif;">

    <!-- WebGL Canvas Container -->
    <canvas id="webgl-canvas" class="fixed inset-0 w-full h-full pointer-events-none z-[-30]"></canvas>

    <!-- Technical Grid Overlay (Dark Mode) -->
    <div class="fixed inset-0 w-full h-full pointer-events-none z-[-20] opacity-[0.06]" style="background-image: repeating-linear-gradient(45deg, rgba(255,255,255,0.8) 0, rgba(255,255,255,0.8) 1px, transparent 1px, transparent 56px);"></div>

    <!-- Cinematic Grain Overlay (Dark Mode) -->
    <div class="fixed inset-0 w-full h-full pointer-events-none z-[-10] mix-blend-overlay opacity-[0.15]" style="background-image: url('data:image/svg+xml,%3Csvg viewBox=%220 0 200 200%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cfilter id=%22noiseFilter%22%3E%3CfeTurbulence type=%22fractalNoise%22 baseFrequency=%220.85%22 numOctaves=%223%22 stitchTiles=%22stitch%22/%3E%3C/filter%3E%3Crect width=%22100%25%22 height=%22100%25%22 filter=%22url(%23noiseFilter)%22/%3E%3C/svg%3E');"></div>

    <!-- Navigation -->
    <nav class="fixed top-0 w-full z-50 px-6 py-6 flex justify-between items-center bg-[#050505]/40 backdrop-blur-lg border-b border-white/5 gsap-reveal">
        <a href="#" class="text-sm font-light tracking-wide text-gray-200 hover:text-white transition-colors duration-300 flex items-center gap-3">
            <span class="w-1.5 h-1.5 rounded-full bg-[#00FFCC] shadow-[0_0_12px_#00FFCC]"></span>
            Vanguard Labs
        </a>
        
        <div class="hidden md:flex gap-8 text-sm font-extralight text-gray-400">
            <a href="#" class="hover:text-cyan-400 transition-colors duration-300">Framework</a>
            <a href="#" class="hover:text-cyan-400 transition-colors duration-300">Architecture</a>
            <a href="#" class="hover:text-cyan-400 transition-colors duration-300">Modules</a>
            <a href="#" class="hover:text-cyan-400 transition-colors duration-300">Transmission</a>
        </div>

        <button class="md:hidden text-gray-400 hover:text-white transition-colors" aria-label="Menu">
            <iconify-icon icon="solar:hamburger-menu-linear" class="text-2xl" stroke-width="1.5"></iconify-icon>
        </button>
    </nav>

    <!-- Main Content -->
    <main class="relative h-screen flex flex-col justify-center px-6 md:px-12 lg:px-24 z-10 pointer-events-none">
        <div class="max-w-2xl pointer-events-auto">
            
            <div class="overflow-hidden mb-6 flex items-center gap-3">
                <span class="relative inline-flex items-center px-3 py-1.5 text-xs font-light text-cyan-300 gsap-reveal-text group z-0">
                    <span class="absolute inset-0 rounded-full bg-gradient-to-r from-cyan-500/20 to-purple-500/20 -z-20"></span>
                    <span class="absolute inset-[1px] rounded-full bg-[#0A0A0A]/90 -z-10 backdrop-blur-sm"></span>
                    <iconify-icon icon="solar:augmented-reality-linear" class="mr-2 text-sm" stroke-width="1.5"></iconify-icon>
                    Dimensional Core v4.5
                </span>
            </div>
            
            <h1 class="text-5xl md:text-6xl lg:text-7xl font-light tracking-tight leading-tight text-white mb-8">
                <span class="inline-block overflow-hidden align-top pb-1"><span class="inline-block masked-word font-semibold">Immersive</span></span>
                <span class="inline-block overflow-hidden align-top pb-1"><span class="inline-block masked-word font-semibold">environments,</span></span>
                <br class="hidden md:block">
                <span class="inline-block overflow-hidden align-top pb-1"><span class="inline-block masked-word font-semibold">engineered</span></span>
                <span class="inline-block overflow-hidden align-top pb-1"><span class="inline-block masked-word font-semibold">with</span></span>
                <br class="hidden md:block">
                <span class="inline-block overflow-hidden align-top pb-1">
                    <span class="inline-block masked-word text-transparent bg-clip-text font-semibold" style="background-image: linear-gradient(120deg, #F3F4F6, #9CA3AF); -webkit-background-clip: text;">absolute</span>
                </span>
                <span class="inline-block overflow-hidden align-top pb-1">
                    <span class="inline-block masked-word text-transparent bg-clip-text font-semibold" style="background-image: linear-gradient(120deg, #00FFCC, #7000FF); -webkit-background-clip: text;">precision.</span>
                </span>
            </h1>

            <p class="text-sm md:text-base text-gray-400 max-w-md font-extralight leading-relaxed mb-10 gsap-reveal-text">
                We build boundary-pushing, physics-enabled digital topologies that merge advanced WebGL with sleek brutalism, crafting the next frontier of immersive computing.
            </p>

            <div class="flex flex-col sm:flex-row gap-5 gsap-reveal-text">
                <a href="#" class="inline-flex items-center justify-center px-6 py-3 text-sm font-medium text-[#050505] bg-white rounded-full hover:bg-gray-200 hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 group shadow-[0_0_20px_rgba(255,255,255,0.15)]">
                    Initialize Directory
                    <iconify-icon icon="solar:arrow-right-linear" class="ml-2 text-lg group-hover:translate-x-1 transition-transform" stroke-width="1.5"></iconify-icon>
                </a>
                <a href="#" class="group relative inline-flex items-center justify-center px-6 py-3 text-sm font-light text-gray-300 rounded-full transition-all duration-300 hover:scale-[1.02] hover:text-white active:scale-[0.98] z-0">
                    <span class="absolute inset-0 rounded-full bg-gradient-to-br from-gray-800 via-gray-700 to-gray-900 group-hover:from-gray-700 group-hover:via-gray-600 group-hover:to-gray-800 transition-colors -z-20"></span>
                    <span class="absolute inset-[1px] rounded-full bg-[#050505]/80 backdrop-blur-md -z-10"></span>
                    Launch Environment
                </a>
            </div>
        </div>
    </main>

    <!-- UI Controls & Indicators -->
    <div class="absolute bottom-0 w-full px-6 py-8 flex justify-between items-end z-10 pointer-events-none gsap-reveal">
        <div class="flex flex-col gap-2">
            <div class="text-xs text-gray-500 font-light tracking-widest uppercase">
                Vector // <span id="coord-display" class="text-cyan-400/80 font-medium tracking-wider">0.0000, 0.0000</span>
            </div>
            
            <!-- Custom Theme Toggle -->
            <div class="flex items-center gap-4 mt-5 pointer-events-auto group cursor-pointer" id="theme-toggle" role="switch" aria-checked="false">
                <span class="text-xs font-light text-gray-500 uppercase tracking-widest group-hover:text-gray-300 transition-colors">Void</span>
                <div class="w-10 h-5 rounded-full bg-gray-800 border border-gray-700 relative transition-all duration-300 flex items-center p-0.5 group-hover:border-gray-500 shadow-inner" id="toggle-track">
                    <div class="w-3.5 h-3.5 rounded-full bg-cyan-400 transform transition-transform duration-300 translate-x-0 shadow-[0_0_8px_#00FFCC]" id="toggle-thumb"></div>
                </div>
                <span class="text-xs font-light text-gray-500 uppercase tracking-widest group-hover:text-gray-300 transition-colors">Aurora</span>
            </div>
        </div>

        <div class="flex flex-col items-center gap-4">
            <span class="text-xs text-gray-500 uppercase tracking-widest font-light" style="writing-mode: vertical-rl;">Descend</span>
            <div class="w-[1px] h-14 bg-gray-800 relative overflow-hidden">
                <div class="scroll-line absolute top-0 left-0 w-full h-full bg-gradient-to-b from-transparent via-cyan-400 to-transparent"></div>
            </div>
        </div>
    </div>

    <script>
        // --- Dark WebGL Architecture ---
        const initWebGL = () => {
            const canvas = document.getElementById('webgl-canvas');
            if (!canvas) return;

            const renderer = new THREE.WebGLRenderer({ 
                canvas, 
                alpha: true, 
                antialias: false 
            });
            renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

            const scene = new THREE.Scene();
            const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 100);
            camera.position.z = 12;

            const uniforms = {
                u_time: { value: 0 },
                u_resolution: { value: new THREE.Vector2() },
                u_color1: { value: new THREE.Color(0.0, 0.8, 0.7) }, // Cyan
                u_color2: { value: new THREE.Color(0.4, 0.0, 0.9) }  // Deep Purple
            };

            const snoiseLogic = `
                vec3 permute(vec3 x) { return mod(((x*34.0)+1.0)*x, 289.0); }
                float snoise(vec2 v){
                    const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
                    vec2 i  = floor(v + dot(v, C.yy) );
                    vec2 x0 = v -   i + dot(i, C.xx);
                    vec2 i1;
                    i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
                    vec4 x12 = x0.xyxy + C.xxzz;
                    x12.xy -= i1;
                    i = mod(i, 289.0);
                    vec3 p = permute( permute( i.y + vec3(0.0, i1.y, 1.0 )) + i.x + vec3(0.0, i1.x, 1.0 ));
                    vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
                    m = m*m ; m = m*m ;
                    vec3 x = 2.0 * fract(p * C.www) - 1.0;
                    vec3 h = abs(x) - 0.5;
                    vec3 ox = floor(x + 0.5);
                    vec3 a0 = x - ox;
                    m *= 1.79284291400159 - 0.85373472095314 * ( a0*a0 + h*h );
                    vec3 g;
                    g.x  = a0.x  * x0.x  + h.x  * x0.y;
                    g.yz = a0.yz * x12.xz + h.yz * x12.yw;
                    return 130.0 * dot(m, g);
                }
            `;

            // --- Dark Background Shader Plane ---
            const bgMaterial = new THREE.ShaderMaterial({
                vertexShader: `void main() { gl_Position = vec4(position, 1.0); }`,
                fragmentShader: `
                    uniform float u_time;
                    uniform vec2 u_resolution;
                    uniform vec3 u_color1;
                    uniform vec3 u_color2;
                    \${snoiseLogic}
                    void main() {
                        vec2 uv = gl_FragCoord.xy / u_resolution.xy;
                        uv.x *= u_resolution.x / u_resolution.y;

                        vec3 baseColor = vec3(0.02, 0.02, 0.03);
                        vec2 st = uv * 0.5;
                        st += vec2(snoise(st + u_time * 0.04), snoise(st - u_time * 0.04)) * 0.4;

                        float beam = smoothstep(0.2, 0.9, snoise(vec2(st.x + st.y * 2.0 - u_time * 0.1, u_time * 0.03)));
                        vec3 glow = mix(u_color1, u_color2, snoise(uv * 2.0 + u_time * 0.15) * 0.5 + 0.5);

                        float dist = distance(gl_FragCoord.xy / u_resolution.xy, vec2(0.5));
                        float vignette = smoothstep(1.5, 0.1, dist);
                        
                        vec3 edgeColor = vec3(0.01, 0.01, 0.015);
                        vec3 colorGlow = mix(baseColor, glow, beam * 0.6);

                        gl_FragColor = vec4(mix(edgeColor, colorGlow, vignette), 1.0);
                    }
                `,
                uniforms,
                depthWrite: false,
                depthTest: false
            });

            const bgMesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), bgMaterial);
            bgMesh.position.z = -15;
            scene.add(bgMesh);

            // --- Dark Glass Sphere Shader ---
            const glassMaterial = new THREE.ShaderMaterial({
                vertexShader: `
                    varying vec3 vNormal;
                    void main() {
                        vNormal = normalize(normalMatrix * normal);
                        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                    }
                `,
                fragmentShader: `
                    uniform float u_time;
                    uniform vec2 u_resolution;
                    uniform vec3 u_color1;
                    uniform vec3 u_color2;
                    varying vec3 vNormal;
                    \${snoiseLogic}
                    void main() {
                        vec2 uv = gl_FragCoord.xy / u_resolution.xy;
                        uv += vNormal.xy * 0.2; 
                        uv.x *= u_resolution.x / u_resolution.y;

                        vec3 baseColor = vec3(0.04, 0.04, 0.06);
                        vec2 st = uv * 0.6;
                        st += vec2(snoise(st + u_time * 0.06), snoise(st - u_time * 0.06)) * 0.35;

                        float beam = smoothstep(0.1, 0.9, snoise(vec2(st.x + st.y * 1.8 - u_time * 0.12, u_time * 0.02)));
                        vec3 glow = mix(u_color1, u_color2, snoise(uv * 1.8 + u_time * 0.12) * 0.5 + 0.5);

                        float fresnel = dot(vec3(0.0, 0.0, 1.0), vNormal);
                        fresnel = clamp(1.0 - fresnel, 0.0, 1.0);
                        fresnel = pow(fresnel, 2.5);

                        vec3 finalColor = mix(baseColor, glow, clamp((beam * 0.5) + (fresnel * 0.8), 0.0, 1.0));
                        gl_FragColor = vec4(finalColor, 0.95);
                    }
                `,
                uniforms,
                transparent: true
            });

            const sphereGeo = new THREE.SphereGeometry(1, 64, 64);
            const spheres = [];

            // Remixed Coordinates and scales
            const sphereData = [
                { scale: 4.2, x: 6.5, y: -1.2, z: -1.5, speed: 0.002 },   
                { scale: 1.8, x: -6.0, y: -4.0, z: 2.5, speed: 0.004 },  
                { scale: 1.1, x: -4.5, y: 4.2, z: -2.0, speed: 0.005 },  
                { scale: 0.75, x: 3.0, y: 5.5, z: 4.0, speed: 0.008 }      
            ];

            sphereData.forEach(data => {
                const mesh = new THREE.Mesh(sphereGeo, glassMaterial);
                mesh.scale.set(data.scale, data.scale, data.scale);
                mesh.position.set(data.x, data.y, data.z);
                scene.add(mesh);
                spheres.push({
                    mesh,
                    baseY: data.y,
                    speed: data.speed,
                    offset: Math.random() * Math.PI * 2
                });
            });

            // --- Viewport Dynamics ---
            let mouseX = 0, mouseY = 0;
            const windowHalfX = window.innerWidth / 2;
            const windowHalfY = window.innerHeight / 2;
            const coordDisplay = document.getElementById('coord-display');

            document.addEventListener('mousemove', (event) => {
                mouseX = (event.clientX - windowHalfX);
                mouseY = (event.clientY - windowHalfY);
                if(coordDisplay) {
                    coordDisplay.innerText = `\${(event.clientX / window.innerWidth).toFixed(4)}, \${(event.clientY / window.innerHeight).toFixed(4)}`;
                }
            });

            const resize = () => {
                const width = window.innerWidth;
                const height = window.innerHeight;
                renderer.setSize(width, height);
                camera.aspect = width / height;
                camera.updateProjectionMatrix();

                const dist = camera.position.z - bgMesh.position.z;
                const vFov = camera.fov * Math.PI / 180;
                const planeHeight = 2 * Math.tan(vFov / 2) * dist;
                bgMesh.scale.set(planeHeight * camera.aspect / 2, planeHeight / 2, 1);
                
                uniforms.u_resolution.value.set(width, height);
            };

            window.addEventListener('resize', resize);
            resize();

            let isAurora = false;
            const themeToggle = document.getElementById('theme-toggle');
            
            themeToggle.addEventListener('click', () => {
                isAurora = !isAurora;
                themeToggle.setAttribute('aria-checked', isAurora.toString());
                const thumb = document.getElementById('toggle-thumb');
                
                if(isAurora) {
                    thumb.style.transform = 'translateX(20px)';
                    thumb.style.backgroundColor = '#FF007F'; // Neon Pink
                    thumb.style.boxShadow = '0 0 8px #FF007F';
                    gsap.to(uniforms.u_color1.value, { r: 1.0, g: 0.0, b: 0.5, duration: 1.5 });
                    gsap.to(uniforms.u_color2.value, { r: 1.0, g: 0.3, b: 0.0, duration: 1.5 });
                } else {
                    thumb.style.transform = 'translateX(0px)';
                    thumb.style.backgroundColor = '#00FFCC'; // Cyan
                    thumb.style.boxShadow = '0 0 8px #00FFCC';
                    gsap.to(uniforms.u_color1.value, { r: 0.0, g: 0.8, b: 0.7, duration: 1.5 });
                    gsap.to(uniforms.u_color2.value, { r: 0.4, g: 0.0, b: 0.9, duration: 1.5 });
                }
            });

            const clock = new THREE.Clock();
            const animate = () => {
                requestAnimationFrame(animate);
                const time = clock.getElapsedTime();
                
                uniforms.u_time.value = time;

                camera.position.x += (mouseX * 0.005 - camera.position.x) * 0.05;
                camera.position.y += (-mouseY * 0.005 - camera.position.y) * 0.05;
                camera.lookAt(scene.position);

                spheres.forEach(s => {
                    s.mesh.position.y = s.baseY + Math.sin(time * s.speed * 120 + s.offset) * 0.5;
                    s.mesh.rotation.x = time * s.speed * 18;
                    s.mesh.rotation.y = time * s.speed * 24;
                });

                renderer.render(scene, camera);
            };

            animate();
        };

        const initUI = () => {
            gsap.registerPlugin(ScrollTrigger);

            const tl = gsap.timeline({ 
                scrollTrigger: {
                    trigger: "main",
                    start: "top 80%",
                },
                defaults: { ease: "power3.out" } 
            });

            gsap.set('.gsap-reveal-text', { y: 24, opacity: 0 });
            gsap.set('.gsap-reveal', { opacity: 0 });
            gsap.set('.masked-word', { y: "110%" });

            tl.to('.gsap-reveal', { opacity: 1, duration: 1.2, delay: 0.2 })
              .to('.gsap-reveal-text', { y: 0, opacity: 1, duration: 1.0, stagger: 0.12 }, "-=1.0")
              .to('.masked-word', { y: "0%", duration: 1.0, stagger: 0.05 }, "-=0.8");

            gsap.to('.scroll-line', {
                yPercent: 150,
                opacity: 0,
                repeat: -1,
                duration: 2.2,
                ease: "power2.inOut",
                onRepeat: function() { gsap.set(this.targets()[0], { yPercent: -100, opacity: 1 }); }
            });
        };

        document.addEventListener('DOMContentLoaded', () => {
            initWebGL();
            initUI();
        });
    </script>

</body>
</html>`;

const DIMENSIONAL_EFFECT: EffectDefinition = {
  title: "Vanguard dimensional architecture",
  source: dimensionalSource,
  background: "#050608",
  targets: [{ selector: "#webgl-canvas", role: "background" }],
};

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

function effectBackground(definition: EffectDefinition, mode: EffectMode) {
  return definition.theme?.[`${mode}Background`] ?? definition.background;
}

function buildFocusedDocument(definition: EffectDefinition, mode: EffectMode) {
  const background = effectBackground(definition, mode);
  const invertBackground =
    definition.theme?.invertBackground === true &&
    definition.theme.nativeMode !== mode;
  const source =
    definition.transformSource?.(definition.source, mode) ?? definition.source;
  const targetJson = JSON.stringify(definition.targets).replace(
    /</g,
    "\\u003c",
  );
  const hiddenTargetJson = JSON.stringify(
    definition.hiddenTargets ?? [],
  ).replace(/</g, "\\u003c");
  const introWordmarkJson = JSON.stringify(
    definition.introWordmark ?? null,
  ).replace(/</g, "\\u003c");
  const modeJson = JSON.stringify(mode);
  const backgroundFilter = invertBackground
    ? "filter: invert(1) hue-rotate(180deg) saturate(.92) brightness(1.02) !important;"
    : "";
  const introWordmarkStyle = definition.introWordmark
    ? `${definition.introWordmark.sceneSelector} .tx { font-size: ${definition.introWordmark.fontSize}px !important; }`
    : "";
  const focusStyle = `<style data-threeui-focus>
html, body { width: 100% !important; height: 100% !important; min-height: 0 !important; margin: 0 !important; padding: 0 !important; overflow: hidden !important; background: ${background} !important; color-scheme: ${mode} !important; }
body { position: relative !important; display: flex !important; align-items: center !important; justify-content: center !important; }
body > * { visibility: hidden !important; }
body[data-threeui-ready] > [data-threeui-role] { visibility: visible !important; }
[data-threeui-residual] { display: none !important; }
[data-threeui-hidden] { display: none !important; }
[data-threeui-role="background"] { position: fixed !important; inset: 0 !important; width: 100% !important; height: 100% !important; max-width: none !important; max-height: none !important; z-index: 0 !important; opacity: 1 !important; pointer-events: none !important; ${backgroundFilter} }
[data-threeui-role="background"][data-threeui-fit="contain-square"] { position: absolute !important; top: 50% !important; right: auto !important; bottom: auto !important; left: 50% !important; width: min(100vw, 100vh) !important; height: min(100vw, 100vh) !important; aspect-ratio: 1 / 1 !important; transform: translate(-50%, -50%) !important; }
[data-threeui-role="button"] { position: relative !important; z-index: 2 !important; opacity: 1 !important; flex: none !important; }
[data-threeui-role="button"]:not([data-threeui-preserve-transform]) { transform: none !important; }
[data-threeui-role="visual"] { position: relative !important; z-index: 1 !important; width: min(100%, 1040px) !important; max-width: 1040px !important; max-height: 100% !important; margin: auto !important; padding: 24px !important; overflow: auto !important; opacity: 1 !important; filter: none !important; }
[data-threeui-role="visual"]:not([data-threeui-preserve-transform]) { transform: none !important; }
[data-threeui-role="visual"][data-threeui-fit="contain-square"] { flex: none !important; width: min(calc(100vw - 32px), calc(100vh - 32px)) !important; max-width: none !important; height: min(calc(100vw - 32px), calc(100vh - 32px)) !important; max-height: none !important; aspect-ratio: 1 / 1 !important; padding: 0 !important; overflow: hidden !important; }
[data-threeui-role="visual"][data-threeui-fit="wide-wordmark"] { width: min(calc(100vw - 48px), 1180px) !important; max-width: calc(100vw - 48px) !important; height: auto !important; max-height: none !important; aspect-ratio: 16 / 3 !important; padding: 0 !important; overflow: hidden !important; }
[data-threeui-role="visual"][data-threeui-fit="portrait-stage"] { position: absolute !important; top: 50% !important; right: auto !important; bottom: auto !important; left: 50% !important; width: 1080px !important; max-width: none !important; height: 1350px !important; max-height: none !important; padding: 0 !important; overflow: hidden !important; transform-origin: center !important; }
${introWordmarkStyle}
</style>`;
  const focusScript = `<script data-threeui-focus>
(function () {
  document.documentElement.dataset.sfMode = ${modeJson};
  var isolated = false;
  function isolate() {
    if (isolated) return;
    var specs = ${targetJson};
    var hiddenSelectors = ${hiddenTargetJson};
    var introWordmark = ${introWordmarkJson};
    var roots = [];
    hiddenSelectors.forEach(function (selector) {
      document.querySelectorAll(selector).forEach(function (element) {
        element.setAttribute('data-threeui-hidden', '');
        element.setAttribute('aria-hidden', 'true');
        if ('inert' in element) element.inert = true;
      });
    });
    specs.forEach(function (spec) {
      var element = document.querySelector(spec.selector);
      if (!element) return;
      element.setAttribute('data-threeui-role', spec.role);
      if (spec.fit) element.setAttribute('data-threeui-fit', spec.fit);
      if (spec.preserveTransform) element.setAttribute('data-threeui-preserve-transform', '');
      if (!roots.some(function (root) { return root.contains(element); })) roots.push(element);
    });
    if (introWordmark) {
      var introScene = document.querySelector(introWordmark.sceneSelector);
      var introText = introScene && introScene.querySelector('.tx');
      var introMark = introText && introText.querySelector('.mark');
      if (introText && introMark) {
        introMark.innerHTML = introWordmark.logoSvg;
        var introCharacters = Array.from(introText.children).filter(function (element) { return element !== introMark; });
        introCharacters.forEach(function (element, index) {
          element.textContent = introWordmark.text[index] === ' ' ? '\u00a0' : (introWordmark.text[index] || '');
          element.style.display = index < introWordmark.text.length ? 'inline-block' : 'none';
        });
      }
      var introReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      var introStartedAt = performance.now();
      function renderIntroWordmark(now) {
        if (typeof window.__seek !== 'function') return;
        if (introReducedMotion) {
          window.__seek(introWordmark.endTime);
          return;
        }
        var introCycle = introWordmark.endTime + introWordmark.holdTime;
        var introTime = ((now - introStartedAt) / 1000) % introCycle;
        window.__seek(Math.min(introTime, introWordmark.endTime));
        requestAnimationFrame(renderIntroWordmark);
      }
      requestAnimationFrame(renderIntroWordmark);
    }
    if (!roots.length) return;
    isolated = true;
    roots.forEach(function (root) {
      var placeholderLink = root.matches('a[href="#"]') ? root : root.querySelector('a[href="#"]');
      if (placeholderLink) placeholderLink.addEventListener('click', function (event) { event.preventDefault(); });
      document.body.appendChild(root);
    });
    Array.from(document.body.children).forEach(function (element) {
      if (roots.indexOf(element) !== -1) return;
      element.setAttribute('data-threeui-residual', '');
      element.setAttribute('aria-hidden', 'true');
      if ('inert' in element) element.inert = true;
    });
    document.body.setAttribute('data-threeui-ready', '');
    requestAnimationFrame(function () { window.dispatchEvent(new Event('resize')); });
  }
  function scheduleIsolation() { setTimeout(isolate, 100); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', scheduleIsolation, { once: true });
  else scheduleIsolation();
  window.addEventListener('load', isolate, { once: true });
})();
</script>`;
  return source
    .replace(/<\/head>/i, `${focusStyle}</head>`)
    .replace(/<\/body>/i, `${focusScript}</body>`);
}

function NeuformIsolatedEffect({
  mode = NEUFORM_ISOLATED_DEFAULTS.mode,
  hue = NEUFORM_ISOLATED_DEFAULTS.hue,
  saturation = NEUFORM_ISOLATED_DEFAULTS.saturation,
  brightness = NEUFORM_ISOLATED_DEFAULTS.brightness,
  className,
  style,
}: DimensionalFieldProps) {
  const safeMode: EffectMode = mode === "light" ? "light" : "dark";
  const definition = DIMENSIONAL_EFFECT;
  const background = effectBackground(definition, safeMode);
  const source = useMemo(
    () => buildFocusedDocument(definition, safeMode),
    [safeMode],
  );
  const safeHue = clamp(hue, -180, 180);
  const safeSaturation = clamp(saturation, 0, 2);
  const safeBrightness = clamp(brightness, 0.35, 1.65);
  const filter =
    safeHue === 0 && safeSaturation === 1 && safeBrightness === 1
      ? undefined
      : `hue-rotate(${safeHue}deg) saturate(${safeSaturation}) brightness(${safeBrightness})`;

  return (
    <iframe
      className={className}
      data-mode={safeMode}
      title={definition.title}
      srcDoc={source}
      sandbox="allow-scripts"
      loading="eager"
      style={{
        display: "block",
        width: "100%",
        height: "100%",
        border: 0,
        background,
        filter,
        ...style,
      }}
    />
  );
}

function DimensionalField(props: DimensionalFieldProps) {
  return <NeuformIsolatedEffect {...props} />;
}

export default DimensionalField;
