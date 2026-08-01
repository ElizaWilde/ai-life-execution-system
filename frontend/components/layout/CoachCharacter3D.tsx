"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

export default function CoachCharacter3D() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, 1, 0.01, 100);
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;

    scene.add(new THREE.HemisphereLight(0xfff8ff, 0x4a355f, 2.5));
    const keyLight = new THREE.DirectionalLight(0xffffff, 3.4);
    keyLight.position.set(3, 5, 4);
    scene.add(keyLight);
    const rimLight = new THREE.DirectionalLight(0xb79aff, 2.2);
    rimLight.position.set(-4, 2, -3);
    scene.add(rimLight);

    let model: THREE.Object3D | null = null;
    let mixer: THREE.AnimationMixer | null = null;
    let disposed = false;
    let pointerX = 0;
    let pointerY = 0;
    let modelBaseY = 0;
    const clock = new THREE.Clock();

    function resize() {
      const width = Math.max(canvas!.clientWidth, 1);
      const height = Math.max(canvas!.clientHeight, 1);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    }

    function frameModel(object: THREE.Object3D) {
      const box = new THREE.Box3().setFromObject(object);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      object.position.sub(center);
      const verticalDistance = size.y / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)));
      const horizontalDistance = size.x / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.aspect);
      const distance = Math.max(verticalDistance, horizontalDistance) * 1.12;
      camera.position.set(0, size.y * 0.04, distance);
      camera.near = Math.max(distance / 100, 0.01);
      camera.far = distance * 100;
      camera.lookAt(0, size.y * 0.02, 0);
      camera.updateProjectionMatrix();
    }

    new GLTFLoader().load(
      "/characters/chibi-witch-character.glb",
      (gltf) => {
        if (disposed) return;
        model = gltf.scene;
        model.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.frustumCulled = false;
            const materials = Array.isArray(child.material) ? child.material : [child.material];
            materials.forEach((material) => { material.side = THREE.DoubleSide; });
          }
        });
        scene.add(model);
        resize();
        frameModel(model);
        modelBaseY = model.position.y;
        if (gltf.animations.length) {
          mixer = new THREE.AnimationMixer(model);
          mixer.clipAction(gltf.animations[0]).play();
        }
      },
      undefined,
      () => setFailed(true),
    );

    function trackPointer(event: PointerEvent) {
      const bounds = canvas!.getBoundingClientRect();
      pointerX = ((event.clientX - bounds.left) / bounds.width - 0.5) * 2;
      pointerY = ((event.clientY - bounds.top) / bounds.height - 0.5) * 2;
    }
    function resetPointer() {
      pointerX = 0;
      pointerY = 0;
    }

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(canvas);
    canvas.addEventListener("pointermove", trackPointer);
    canvas.addEventListener("pointerleave", resetPointer);

    let animationFrame = 0;
    function render() {
      animationFrame = requestAnimationFrame(render);
      const delta = Math.min(clock.getDelta(), 0.05);
      const elapsed = clock.elapsedTime;
      mixer?.update(delta);
      if (model) {
        model.rotation.y += (pointerX * 0.28 - model.rotation.y) * 0.055;
        model.rotation.x += (-pointerY * 0.06 - model.rotation.x) * 0.045;
        const targetY = modelBaseY + Math.sin(elapsed * 1.6) * 0.012;
        model.position.y += (targetY - model.position.y) * 0.035;
      }
      renderer.render(scene, camera);
    }
    resize();
    render();

    return () => {
      disposed = true;
      cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      canvas.removeEventListener("pointermove", trackPointer);
      canvas.removeEventListener("pointerleave", resetPointer);
      scene.traverse((child) => {
        if (!(child instanceof THREE.Mesh)) return;
        child.geometry.dispose();
        const materials = Array.isArray(child.material) ? child.material : [child.material];
        materials.forEach((material) => material.dispose());
      });
      renderer.dispose();
    };
  }, []);

  return failed
    ? <span className="coach-character-fallback" aria-hidden="true">✦</span>
    : <canvas aria-label="Interactive 3D AI Coach character" ref={canvasRef} />;
}
