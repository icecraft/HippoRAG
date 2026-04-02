import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import {
  HomeOutlined,
  BookOutlined,
  TeamOutlined,
  UploadOutlined,
  SearchOutlined,
  MonitorOutlined,
} from '@ant-design/icons';

const { Sider, Content, Header } = Layout;

const menuItems = [
  {
    key: '/',
    icon: <HomeOutlined />,
    label: '首页',
  },
  {
    key: '/query',
    icon: <SearchOutlined />,
    label: '知识查询',
  },
  {
    key: '/books',
    icon: <BookOutlined />,
    label: '书籍管理',
  },
  {
    key: '/businesses',
    icon: <TeamOutlined />,
    label: '业务管理',
  },
  {
    key: '/ingest',
    icon: <UploadOutlined />,
    label: '文档上传',
  },
  {
    key: '/ingest/status',
    icon: <MonitorOutlined />,
    label: '索引任务',
  },
];

const AppLayout = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();

  const handleMenuClick = ({ key }) => {
    navigate(key);
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="light" width={200}>
        <div style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderBottom: '1px solid #f0f0f0',
          fontWeight: 'bold',
          fontSize: 18,
        }}>
          HippoRAG
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{ borderRight: 0 }}
        />
      </Sider>
      <Layout>
        <Header style={{
          background: '#fff',
          padding: '0 24px',
          borderBottom: '1px solid #f0f0f0',
        }}>
          <h2 style={{ margin: 0, lineHeight: '64px' }}>
            {menuItems.find((item) => item.key === location.pathname)?.label || 'HippoRAG'}
          </h2>
        </Header>
        <Content style={{
          margin: 24,
          padding: 24,
          background: '#fff',
          borderRadius: 8,
          minHeight: 280,
        }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
