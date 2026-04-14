import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { GameSessionProvider } from "@/context/GameSessionContext";
import { ActivityGate } from "@/components/ActivityGate";
import Index from "./pages/Index.tsx";
import BattlePreviewDemo from "./pages/BattlePreviewDemo.tsx";
import NotFound from "./pages/NotFound.tsx";

const App = () => (
  <GameSessionProvider>
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
