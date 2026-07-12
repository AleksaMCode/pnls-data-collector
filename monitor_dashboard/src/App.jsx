import Login from './components/auth/login';

import { Navigate, useRoutes } from 'react-router-dom';
import { AuthProvider } from './context/authContext';
import ProtectedRoute from './components/protectedRoute';
import PublicRoute from './components/publicRoute';
import Dashboard from './components/dashboard/Dashboard';
import { ToastContainer } from 'react-toastify';
import DeviceView from './components/dashboard/DeviceView';
import MainGrid from './components/dashboard/MainGrid';
import SsidView from './components/dashboard/SsidView';

function App() {
  const routesArray = [
    {
      path: '*',
      element: (
        <PublicRoute>
          <Login />
        </PublicRoute>
      ),
    },
    {
      path: '/login',
      element: (
        <PublicRoute>
          <Login />
        </PublicRoute>
      ),
    },
    {
      path: '/',
      element: (
        <ProtectedRoute>
          <Dashboard />
        </ProtectedRoute>
      ),
      children: [
        {
          index: true,
          element: <Navigate to="home" replace />,
        },
        { path: 'home', element: <MainGrid /> },
        { path: 'ssids', element: <SsidView /> },
        { path: 'device/:deviceId', element: <DeviceView /> },
      ],
    },
  ];
  let routesElement = useRoutes(routesArray);
  return (
    <AuthProvider>
      {}
      <ToastContainer
        position="top-center"
        autoClose={4000}
        newestOnTop
        closeOnClick
        pauseOnHover
      />
      <div className="w-full h-screen flex flex-col">{routesElement}</div>
    </AuthProvider>
  );
}

export default App;
