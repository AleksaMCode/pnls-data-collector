import { Navigate } from 'react-router-dom';
import { useAuth } from '../../context/authContext';

const PublicRoute = ({ children }) => {
  const { userLoggedIn, loading } = useAuth();

  if (loading) return null;

  return userLoggedIn ? <Navigate to="/home" replace /> : children;
};

export default PublicRoute;
