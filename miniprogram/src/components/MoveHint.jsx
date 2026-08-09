import { Text, View } from "@tarojs/components";

/** Small status pill explaining the two-tap move interaction. */
export default function MoveHint({ selected, myTurn, waiting }) {
  const text = waiting ? "等待对方加入房间" : !myTurn ? "等待对方行棋" : selected ? "再点一个目标格完成移动" : "先点自己的棋子，再点目标格";
  return <View className="animal-move-hint"><Text>{text}</Text></View>;
}
