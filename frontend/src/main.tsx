import React from 'react'
import ReactDOM from 'react-dom/client'
import {
  createBrowserRouter,
  RouterProvider,
} from 'react-router-dom';
import './index.css'
import { store } from './store'
import { Provider } from 'react-redux'
import Root from './Root.tsx'
import Login from './Login.tsx';
import Auth from './Auth.tsx';
import Home from './Home.tsx';

const router = createBrowserRouter([
  {
    path: '/',
    element: <Root />,
    children: [
      {
        path: 'login',
        element: <Login />,
      },
      {
        path: 'auth',
        element: <Auth />,
      },
      {
        path: 'home',
        element: <Home />,
      }
    ],
  },
]);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Provider store={store}>
      <RouterProvider router={router} />
    </Provider>
  </React.StrictMode>
)
