import { useEffect, useState } from "react";
import { api } from "./lib/apiClient";

function App() {
  const [health, setHealth] = useState<string>("checking…");

  useEffect(() => {
    api
      .get<{ status: string }>("/api/health")
      .then((res) => setHealth(res.data.status))
      .catch(() => setHealth("unreachable"));
  }, []);

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem" }}>
      <h1>SafetyReady</h1>
      <p>
        API status: <strong>{health}</strong>
      </p>
    </main>
  );
}

export default App;
