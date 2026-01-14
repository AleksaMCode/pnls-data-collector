import { Navigate } from 'react-router-dom';
import { useAuth } from '../../context/authContext';

const ProtectedRoute = ({ children }) => {
  const { userLoggedIn } = useAuth();

  return userLoggedIn ? children : <Navigate to="/login" replace />;
};

export default ProtectedRoute;
