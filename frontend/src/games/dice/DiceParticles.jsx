import { Sparkles } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useRef } from "react";

/**
 * Adds restrained blue and pink motes that intensify while the cup is shaking.
 */
export default function DiceParticles({ rolling }) {
  const groupRef = useRef(null);

  useFrame(({ clock }) => {
    if (!groupRef.current) {
      return;
    }
    const time = clock.getElapsedTime();
    groupRef.current.rotation.y = time * (rolling ? 0.32 : 0.08);
    groupRef.current.position.y = 0.45 + Math.sin(time * 1.4) * 0.08;
  });

  return (
    <group ref={groupRef}>
      <Sparkles
        count={rolling ? 54 : 18}
        scale={[7.5, 2.2, 7.5]}
        size={rolling ? 3.4 : 2}
        speed={rolling ? 1.15 : 0.22}
        noise={[1.4, 0.7, 1.4]}
        color="#79cfff"
        opacity={rolling ? 0.72 : 0.24}
      />
      <Sparkles
        count={rolling ? 24 : 8}
        scale={[6, 1.5, 6]}
        size={2.6}
        speed={rolling ? 0.8 : 0.16}
        color="#ef7695"
        opacity={rolling ? 0.48 : 0.16}
      />
    </group>
  );
}
