import {
  createContext,
  lazy,
  Suspense,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import AdminRoute from "./components/AdminRoute";
import Admin from "./pages/Admin";
import AdminLogin from "./pages/AdminLogin";
import AdminStats from "./pages/AdminStats";
import Cart from "./pages/Cart";
import DishDetail from "./pages/DishDetail";
import DishManage from "./pages/DishManage";
import Home from "./pages/Home";
import MyOrders from "./pages/MyOrders";
import NotFound from "./pages/NotFound";
import OrderStatus from "./pages/OrderStatus";
import { getCustomerId } from "./utils/customer";

const DiceGame = lazy(() => import("./games/dice/DiceGame"));

const CartContext = createContext(null);

export const useCart = () => useContext(CartContext);

export default function App() {
  const [cart, setCart] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("girlfriend-menu-cart")) || [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    localStorage.setItem("girlfriend-menu-cart", JSON.stringify(cart));
  }, [cart]);

  useEffect(() => {
    getCustomerId();
  }, []);

  const cartApi = useMemo(
    () => ({
      cart,
      addItem(dish) {
        setCart((items) => {
          const found = items.find((item) => item.id === dish.id);
          return found
            ? items.map((item) =>
                item.id === dish.id ? { ...item, quantity: item.quantity + 1 } : item,
              )
            : [...items, { ...dish, quantity: 1 }];
        });
      },
      setQuantity(id, quantity) {
        setCart((items) =>
          quantity <= 0
            ? items.filter((item) => item.id !== id)
            : items.map((item) => (item.id === id ? { ...item, quantity } : item)),
        );
      },
      clearCart() {
        setCart([]);
      },
      count: cart.reduce((sum, item) => sum + item.quantity, 0),
    }),
    [cart],
  );

  return (
    <CartContext.Provider value={cartApi}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route path="/dishes/:id" element={<DishDetail />} />
          <Route path="/cart" element={<Cart />} />
          <Route path="/my-orders" element={<MyOrders />} />
          <Route path="/orders/:id" element={<OrderStatus />} />
          <Route
            path="/games/dice"
            element={(
              <Suspense fallback={<div className="state-box route-loading">3D 骰子桌正在布置…</div>}>
                <DiceGame />
              </Suspense>
            )}
          />
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route element={<AdminRoute />}>
            <Route path="/admin" element={<Admin />} />
            <Route path="/admin/dishes" element={<DishManage />} />
            <Route path="/admin/stats" element={<AdminStats />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </CartContext.Provider>
  );
}
