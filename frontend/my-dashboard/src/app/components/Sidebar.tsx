export default function Sidebar() {
  return (
    <aside className="w-64 bg-gray-800 text-gray-100 h-screen p-6 flex flex-col">
      <h2 className="text-2xl font-bold mb-8 text-blue-400">DevOps</h2>
      <nav className="flex flex-col gap-4">
        <a href="#" className="hover:text-blue-400">Dashboard</a>
        <a href="#" className="hover:text-blue-400">Deploy</a>
        <a href="#" className="hover:text-blue-400">Health Check</a>
        <a href="#" className="hover:text-blue-400">Settings</a>
      </nav>
    </aside>
  );
}