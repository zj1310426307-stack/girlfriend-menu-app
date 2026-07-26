import { useFrame } from "@react-three/fiber";
import { useRef } from "react";
import { MathUtils, Vector3 } from "three";

import { useLeatherMaterialMap } from "./materials";

const RESTING_POSITION = new Vector3(7.2, 1.1, -5.4);
const SHAKING_POSITION = new Vector3(0, 1.72, 0);

/**
 * Renders and animates the leather-like dice cup above the physical dice.
 */
export default function DiceCup({ rolling, gestureOffset = 0, gestureActive = false }) {
  const groupRef = useRef(null);
  const leatherMap = useLeatherMaterialMap();

  useFrame(({ clock }, delta) => {
    if (!groupRef.current) {
      return;
    }
    const time = clock.getElapsedTime();
    const manuallyShaking = gestureActive && !rolling;
    const target = rolling || manuallyShaking ? SHAKING_POSITION : RESTING_POSITION;
    groupRef.current.position.lerp(target, 1 - Math.exp(-delta * 5.5));
    if (manuallyShaking) {
      groupRef.current.position.x += gestureOffset * 1.45;
    }
    groupRef.current.rotation.x = MathUtils.damp(
      groupRef.current.rotation.x,
      rolling
        ? Math.sin(time * 23) * 0.075
        : manuallyShaking
          ? gestureOffset * 0.12
          : -0.18,
      7,
      delta,
    );
    groupRef.current.rotation.z = MathUtils.damp(
      groupRef.current.rotation.z,
      rolling
        ? Math.sin(time * 29) * 0.11
        : manuallyShaking
          ? -gestureOffset * 0.16
          : 0.26,
      7,
      delta,
    );
    if (rolling) {
      groupRef.current.position.y += Math.abs(Math.sin(time * 21)) * 0.055;
    }
  });

  return (
    <group ref={groupRef} position={RESTING_POSITION.toArray()} rotation={[-0.18, 0, 0.26]}>
      <mesh castShadow receiveShadow>
        <cylinderGeometry args={[2.12, 2.72, 3.35, 64, 1, false]} />
        <meshPhysicalMaterial
          color="#111523"
          roughness={0.54}
          roughnessMap={leatherMap}
          bumpMap={leatherMap}
          bumpScale={0.065}
          metalness={0.03}
          clearcoat={0.32}
          clearcoatRoughness={0.42}
          envMapIntensity={0.95}
          side={2}
        />
      </mesh>
      <mesh scale={[0.93, 0.98, 0.93]} castShadow>
        <cylinderGeometry args={[2.12, 2.72, 3.35, 64, 1, true]} />
        <meshStandardMaterial color="#29181d" roughness={0.82} side={1} />
      </mesh>
      {Array.from({ length: 12 }, (_, index) => {
        const angle = (index / 12) * Math.PI * 2;
        return (
          <mesh
            key={index}
            position={[Math.sin(angle) * 2.53, -1.25, Math.cos(angle) * 2.53]}
            rotation={[0, angle, 0]}
          >
            <sphereGeometry args={[0.035, 10, 8]} />
            <meshStandardMaterial color="#8ba0bd" roughness={0.45} metalness={0.5} />
          </mesh>
        );
      })}
      <mesh position={[0, -1.68, 0]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <torusGeometry args={[2.69, 0.09, 18, 64]} />
        <meshStandardMaterial color="#486e9d" roughness={0.32} metalness={0.58} />
      </mesh>
      <mesh position={[0, 1.68, 0]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <torusGeometry args={[2.1, 0.075, 18, 64]} />
        <meshStandardMaterial color="#283b59" roughness={0.3} metalness={0.5} />
      </mesh>
    </group>
  );
}
