import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { GameSessionProvider } from "@/context/GameSessionContext";
import type { AuthProvider } from "@/context/auth/types";
import { ActivityGate } from "@/components/ActivityGate";
import Index from "./pages/Index.tsx";
import BattlePreviewDemo from "./pages/BattlePreviewDemo.tsx";
import NotFound from "./pages/NotFound.tsx";

/** authProvider is injected by non-Discord shells (mobile). Omitted → the
 *  provider defaults to the embedded Discord Activity login. */
const App = ({ authProvider }: { authProvider?: AuthProvider } = {}) => (
  <GameSessionProvider authProvider={authProvider}>
    <TooltipProvider>
      <Toaster />
      <Sonner position="top-right" />
      <ActivityGate>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="/battle-preview-demo" element={<BattlePreviewDemo />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </ActivityGate>
    </TooltipProvider>
  </GameSessionProvider>
);

export default App;
