import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Row, Col, Statistic, Spin, Alert } from 'antd';
import {
  BookOutlined,
  TeamOutlined,
  UploadOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { checkHealth, getBooks, getBusinesses } from '../../api';

const Home = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState(null);
  const [stats, setStats] = useState({ bookCount: 0, businessCount: 0 });
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [healthRes, booksRes, businessesRes] = await Promise.all([
          checkHealth(),
          getBooks(),
          getBusinesses(),
        ]);
        setHealth(healthRes.data);
        setStats({
          bookCount: booksRes.data.books?.length || 0,
          businessCount: businessesRes.data.businesses?.length || 0,
        });
        setError(null);
      } catch (err) {
        setError('无法连接到后端服务，请确保 API 服务已启动');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      {error && (
        <Alert
          message="连接错误"
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: 24 }}
        />
      )}

      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card>
            <Statistic
              title="系统状态"
              value={health?.status === 'healthy' ? '正常运行' : '异常'}
              prefix={<CheckCircleOutlined style={{ color: health?.status === 'healthy' ? '#52c41a' : '#ff4d4f' }} />}
              valueStyle={{ color: health?.status === 'healthy' ? '#52c41a' : '#ff4d4f' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={8}>
          <Card
            hoverable
            onClick={() => navigate('/books')}
            style={{ textAlign: 'center' }}
          >
            <Statistic
              title="书籍总数"
              value={stats.bookCount}
              prefix={<BookOutlined />}
            />
            <div style={{ marginTop: 16, color: '#1890ff' }}>点击管理</div>
          </Card>
        </Col>
        <Col span={8}>
          <Card
            hoverable
            onClick={() => navigate('/businesses')}
            style={{ textAlign: 'center' }}
          >
            <Statistic
              title="业务总数"
              value={stats.businessCount}
              prefix={<TeamOutlined />}
            />
            <div style={{ marginTop: 16, color: '#1890ff' }}>点击管理</div>
          </Card>
        </Col>
        <Col span={8}>
          <Card
            hoverable
            onClick={() => navigate('/ingest')}
            style={{ textAlign: 'center' }}
          >
            <Statistic
              title="文档上传"
              value="上传"
              prefix={<UploadOutlined />}
              valueStyle={{ fontSize: 24 }}
            />
            <div style={{ marginTop: 16, color: '#1890ff' }}>点击上传</div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Home;
