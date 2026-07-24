import "@/App.css";
import ComplaintPage from "@/pages/ComplaintPage";
import { Toaster } from "@/components/ui/sonner";

function App() {
  return (
    <div className="App">
      <ComplaintPage />
      <Toaster position="top-right" richColors />
    </div>
  );
}

export default App;
