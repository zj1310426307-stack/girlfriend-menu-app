import { Environment } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Suspense, useCallback, useEffect, useRef } from "react";
import {
  ACESFilmicToneMapping,
  MathUtils,
  SRGBColorSpace,
  Vector3,
} from "three";

import DiceCup from "./DiceCup";
import DiceParticles from "./DiceParticles";
import PhysicsWorld from "./PhysicsWorld";
import { useFeltMaterialMaps } from "./materials";
import { playDiceHit } from "./sounds";

/**
 * Draws the circular blue bar tray shared by all player simulations.
 */
function BarTable() {
  const feltMaps = useFeltMaterialMaps();

  return (
    <group>
      <mesh position={[0, -0.32, 0]} receiveShadow>
        <cylinderGeometry args={[4.68, 4.9, 0.48, 72]} />
        <meshPhysicalMaterial
          color="#0c315a"
          roughness={0.38}
          metalness={0.22}
          clearcoat={0.66}
          clearcoatRoughness={0.24}
        />
      </mesh>
      <mesh position={[0, -0.045, 0]} receiveShadow>
        <cylinderGeometry args={[4.48, 4.58, 0.12, 72]} />
        <meshPhysicalMaterial
          color="#ffffff"
          map={feltMaps.colorMap}
          roughness={0.72}
          roughnessMap={feltMaps.bumpMap}
          bumpMap={feltMaps.bumpMap}
          bumpScale={0.055}
          metalness={0.08}
          clearcoat={0.2}
          clearcoatRoughness={0.68}
          envMapIntensity={0.85}
        />
      </mesh>
      <mesh position={[0, 0.03, 0]} rotation={[Math.PI / 2, 0, 0]} receiveShadow>
        <torusGeometry args={[4.5, 0.1, 20, 72]} />
        <meshPhysicalMaterial
          color="#4b9bc2"
          roughness={0.24}
          metalness={0.64}
          clearcoat={0.7}
          envMapIntensity={1.25}
        />
      </mesh>
      <mesh position={[0, -0.58, 0]} receiveShadow>
        <cylinderGeometry args={[8, 8, 0.18, 64]} />
        <meshStandardMaterial color="#080b14" roughness={0.92} />
      </mesh>
    </group>
  );
}

/**
 * Adds restrained camera movement from device tilt and collision impulses.
 */
function CameraRig({ deviceTilt, rolling, shakeEnergyRef }) {
  const { camera } = useThree();
  const basePosition = useRef(new Vector3(0, 8.1, 10.4));
  const lookTarget = useRef(new Vector3(0, 0.2, 0));

  useEffect(() => {
    if (rolling) {
      shakeEnergyRef.current = Math.max(shakeEnergyRef.current, 0.12);
    }
  }, [rolling, shakeEnergyRef]);

  useFrame((_, delta) => {
    const tiltX = MathUtils.clamp(deviceTilt?.gamma || 0, -25, 25) * 0.018;
    const tiltY = MathUtils.clamp(deviceTilt?.beta || 0, -25, 25) * 0.009;
    const energy = shakeEnergyRef.current;
    const targetX = basePosition.current.x + tiltX + (Math.random() - 0.5) * energy;
    const targetY = basePosition.current.y + tiltY + (Math.random() - 0.5) * energy * 0.6;
    const targetZ = basePosition.current.z + (Math.random() - 0.5) * energy;
    camera.position.x = MathUtils.damp(camera.position.x, targetX, 8, delta);
    camera.position.y = MathUtils.damp(camera.position.y, targetY, 8, delta);
    camera.position.z = MathUtils.damp(camera.position.z, targetZ, 8, delta);
    camera.lookAt(lookTarget.current);
    shakeEnergyRef.current = Math.max(0, energy - delta * 0.42);
  });

  return null;
}

/**
 * Hosts the lazy-loaded Three.js canvas and all independent player physics worlds.
 */
export default function DiceScene({
  players,
  roundId,
  rolling,
  onPlayerSettled,
  deviceTilt,
  gestureOffset,
  gestureActive,
  onGestureStart,
  onGestureMove,
  onGestureEnd,
  onGestureCancel,
}) {
  const shakeEnergyRef = useRef(0);
  const handleHit = useCallback((impact) => {
    const force = impact?.force || 18;
    shakeEnergyRef.current = Math.min(0.24, shakeEnergyRef.current + force / 480);
    playDiceHit(force);
  }, []);

  return (
    <div
      className={`dice-canvas-shell ${gestureActive ? "gesture-active" : ""}`}
      aria-label="3D 大话骰桌面"
      onPointerDown={onGestureStart}
      onPointerMove={onGestureMove}
      onPointerUp={onGestureEnd}
      onPointerCancel={onGestureCancel}
    >
      <Canvas
        shadows
        dpr={[1, 1.5]}
        camera={{ position: [0, 8.1, 10.4], fov: 41, near: 0.1, far: 60 }}
        gl={{
          antialias: true,
          powerPreference: "high-performance",
          toneMapping: ACESFilmicToneMapping,
          outputColorSpace: SRGBColorSpace,
        }}
        onCreated={({ gl }) => {
          gl.toneMappingExposure = 1.08;
        }}
        fallback={<div className="dice-webgl-error">当前浏览器不支持 3D 场景。</div>}
      >
        <color attach="background" args={["#050714"]} />
        <fog attach="fog" args={["#050714", 12, 25]} />
        <ambientLight intensity={0.46} color="#b9c9ea" />
        <hemisphereLight intensity={0.62} color="#cde5ff" groundColor="#080a12" />
        <spotLight
          position={[-4, 9, 5]}
          angle={0.5}
          penumbra={0.8}
          intensity={80}
          color="#eaf5ff"
          castShadow
          shadow-mapSize-width={1024}
          shadow-mapSize-height={1024}
          shadow-bias={-0.0002}
        />
        <pointLight position={[5, 3.5, -3]} intensity={18} color="#ec6688" distance={13} />
        <Suspense fallback={null}>
          <Environment
            files="/textures/warm_bar_1k.hdr"
            background={false}
            environmentIntensity={1.05}
          />
          <CameraRig
            deviceTilt={deviceTilt}
            rolling={rolling}
            shakeEnergyRef={shakeEnergyRef}
          />
          <BarTable />
          <DiceParticles rolling={rolling} />
          {roundId > 0 &&
            players.map((player) => (
              <PhysicsWorld
                key={`${roundId}-${player.id}`}
                playerId={player.id}
                roundId={roundId}
                visible={player.id === "me"}
                onSettled={onPlayerSettled}
                onHit={handleHit}
              />
            ))}
          <DiceCup
            rolling={rolling}
            gestureOffset={gestureOffset}
            gestureActive={gestureActive}
          />
        </Suspense>
      </Canvas>
      <div className="dice-scene-vignette" aria-hidden="true" />
    </div>
  );
}
