import { Admin, Resource, CustomRoutes } from 'react-admin';
import { Route } from 'react-router-dom';
import { dataProvider } from './providers/dataProvider';
import { Dashboard } from './pages/Dashboard';
import { UserList, UserEdit } from './pages/Users';
import { ChatInterface } from './pages/ChatInterface';
import PeopleIcon from '@mui/icons-material/People';

const App = () => (
  <Admin
    dataProvider={dataProvider}
    dashboard={Dashboard}
    title="Shri Travels Admin"
  >
    <Resource
      name="users"
      list={UserList}
      edit={UserEdit}
      icon={PeopleIcon}
      options={{ label: 'Customers' }}
    />
    <CustomRoutes>
      <Route path="/chat" element={<ChatInterface />} />
      <Route path="/chat/:userId" element={<ChatInterface />} />
    </CustomRoutes>
  </Admin>
);

export default App;
