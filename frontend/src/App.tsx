import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Home } from "./pages/Home";
import { Story } from "./pages/Story";
import "./index.css";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/story/:id" element={<Story />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
