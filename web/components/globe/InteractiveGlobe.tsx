"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { formatCurrency } from "@/lib/format";
import type { GlobeRoute } from "@/components/globe/routes";

type InteractiveGlobeProps = {
  routes: GlobeRoute[];
};

const statusColor: Record<GlobeRoute["status"], number> = {
  good: 0x46a758,
  watch: 0xd97757,
  blocked: 0xe5484d,
};

function latLngToVector(lat: number, lng: number, radius: number) {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lng + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -(radius * Math.sin(phi) * Math.cos(theta)),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  );
}

function routeCurve(from: [number, number], to: [number, number], radius: number) {
  const start = latLngToVector(from[0], from[1], radius);
  const end = latLngToVector(to[0], to[1], radius);
  const mid = start.clone().add(end).normalize().multiplyScalar(radius * 1.28);
  return new THREE.QuadraticBezierCurve3(start, mid, end);
}

function createRouteObject(route: GlobeRoute, radius: number) {
  const curve = routeCurve(route.from, route.to, radius);
  const points = curve.getPoints(48);
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  const material = new THREE.LineBasicMaterial({
    color: statusColor[route.status],
    transparent: true,
    opacity: route.status === "good" ? 0.75 : 1,
  });
  const line = new THREE.Line(geometry, material);
  line.userData = { routeId: route.id };
  return line;
}

function createPin(position: [number, number], color: number, radius: number) {
  const geometry = new THREE.SphereGeometry(0.025, 16, 16);
  const material = new THREE.MeshBasicMaterial({ color });
  const pin = new THREE.Mesh(geometry, material);
  pin.position.copy(latLngToVector(position[0], position[1], radius + 0.012));
  return pin;
}

export function InteractiveGlobe({ routes }: InteractiveGlobeProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [selectedRouteId, setSelectedRouteId] = useState(routes[0]?.id ?? "");
  const selectedRoute = useMemo(
    () => routes.find((route) => route.id === selectedRouteId) ?? routes[0],
    [routes, selectedRouteId],
  );

  useEffect(() => {
    if (!containerRef.current || !canvasRef.current) {
      return;
    }

    const container = containerRef.current;
    const canvas = canvasRef.current;
    const scene = new THREE.Scene();
    const globeGroup = new THREE.Group();
    scene.add(globeGroup);
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      preserveDrawingBuffer: true,
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    camera.position.set(0, 0, 3.4);

    const globeRadius = 1;
    const globe = new THREE.Mesh(
      new THREE.SphereGeometry(globeRadius, 64, 64),
      new THREE.MeshStandardMaterial({
        color: 0x181818,
        roughness: 0.92,
        metalness: 0.05,
      }),
    );
    globeGroup.add(globe);

    const wire = new THREE.Mesh(
      new THREE.SphereGeometry(globeRadius + 0.003, 32, 16),
      new THREE.MeshBasicMaterial({
        color: 0x3a3a3a,
        wireframe: true,
        transparent: true,
        opacity: 0.22,
      }),
    );
    globeGroup.add(wire);

    const routeObjects = routes.map((route) => createRouteObject(route, globeRadius + 0.025));
    const pins = routes.flatMap((route) => [
      createPin(route.from, statusColor[route.status], globeRadius),
      createPin(route.to, statusColor[route.status], globeRadius),
    ]);
    routeObjects.forEach((route) => globeGroup.add(route));
    pins.forEach((pin) => globeGroup.add(pin));

    scene.add(new THREE.AmbientLight(0xffffff, 1.8));
    const light = new THREE.DirectionalLight(0xffffff, 1.2);
    light.position.set(2, 1, 3);
    scene.add(light);

    const raycaster = new THREE.Raycaster();
    raycaster.params.Line = { threshold: 0.045 };
    const pointer = new THREE.Vector2();
    let frame = 0;
    let dragging = false;
    let lastX = 0;

    function resize() {
      const rect = container.getBoundingClientRect();
      renderer.setSize(rect.width, rect.height, false);
      camera.aspect = rect.width / Math.max(rect.height, 1);
      camera.updateProjectionMatrix();
    }

    function pickRoute(event: PointerEvent) {
      const rect = canvas.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(routeObjects, false)[0];
      if (hit?.object.userData.routeId) {
        setSelectedRouteId(String(hit.object.userData.routeId));
      }
    }

    function onPointerDown(event: PointerEvent) {
      dragging = true;
      lastX = event.clientX;
      canvas.setPointerCapture(event.pointerId);
    }

    function onPointerMove(event: PointerEvent) {
      if (!dragging) {
        return;
      }
      const delta = event.clientX - lastX;
      lastX = event.clientX;
      globeGroup.rotation.y += delta * 0.006;
    }

    function onPointerUp(event: PointerEvent) {
      dragging = false;
      canvas.releasePointerCapture(event.pointerId);
      pickRoute(event);
    }

    function animate() {
      frame = requestAnimationFrame(animate);
      if (!dragging) {
        globeGroup.rotation.y += 0.0012;
      }
      renderer.render(scene, camera);
    }

    resize();
    animate();
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    canvas.addEventListener("pointerdown", onPointerDown);
    canvas.addEventListener("pointermove", onPointerMove);
    canvas.addEventListener("pointerup", onPointerUp);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      canvas.removeEventListener("pointerdown", onPointerDown);
      canvas.removeEventListener("pointermove", onPointerMove);
      canvas.removeEventListener("pointerup", onPointerUp);
      routeObjects.forEach((route) => {
        route.geometry.dispose();
        (route.material as THREE.Material).dispose();
      });
      pins.forEach((pin) => {
        pin.geometry.dispose();
        (pin.material as THREE.Material).dispose();
      });
      globe.geometry.dispose();
      (globe.material as THREE.Material).dispose();
      wire.geometry.dispose();
      (wire.material as THREE.Material).dispose();
      renderer.dispose();
    };
  }, [routes]);

  return (
    <div className="grid min-h-[520px] grid-cols-[minmax(0,1fr)_320px] border-b border-[var(--color-border)] max-lg:grid-cols-1">
      <div ref={containerRef} className="min-h-[520px] bg-[var(--color-bg)]">
        <canvas
          ref={canvasRef}
          aria-label="Interactive supply chain route globe"
          className="block h-full w-full"
          data-testid="supply-globe-canvas"
        />
      </div>

      <aside className="border-l border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm font-semibold">Routes</p>
          <span className="tnum text-xs text-[var(--color-text-muted)]">{routes.length}</span>
        </div>
        <div className="space-y-2">
          {routes.map((route) => (
            <button
              key={route.id}
              type="button"
              onClick={() => setSelectedRouteId(route.id)}
              className={`w-full rounded border p-3 text-left text-sm transition-colors ${
                selectedRoute?.id === route.id
                  ? "border-[var(--color-info)] bg-[var(--color-surface-raised)]"
                  : "border-[var(--color-border)] bg-[var(--color-bg)] hover:border-[var(--color-border-strong)]"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">{route.origin} to {route.destination}</span>
                <span
                  className={
                    route.status === "good"
                      ? "text-[var(--color-ok)]"
                      : route.status === "watch"
                        ? "text-[var(--color-warn)]"
                        : "text-[var(--color-critical)]"
                  }
                >
                  {route.status}
                </span>
              </div>
              <p className="tnum mt-2 text-xs text-[var(--color-text-muted)]">
                {formatCurrency(route.exposure)} exposure
              </p>
            </button>
          ))}
        </div>

        {selectedRoute ? (
          <div className="mt-5 rounded border border-[var(--color-border)] bg-[var(--color-bg)] p-3">
            <p className="text-sm font-semibold">{selectedRoute.id}</p>
            <p className="mt-2 text-sm leading-5 text-[var(--color-text-muted)]">
              {selectedRoute.reason}
            </p>
            <div className="mt-4 border-t border-[var(--color-border)] pt-3">
              <p className="text-xs text-[var(--color-text-muted)]">Suggestion</p>
              <p className="mt-1 text-sm leading-5">{selectedRoute.recommendation}</p>
            </div>
          </div>
        ) : null}
      </aside>
    </div>
  );
}
