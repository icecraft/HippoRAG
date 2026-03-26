import React, { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, message, Tag, Popconfirm, Space } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined, TeamOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { getBusinesses, createBusiness, deleteBusiness } from '../../api';

const { TextArea } = Input;

const Businesses = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [businesses, setBusinesses] = useState([]);
  const [modalVisible, setModalVisible] = useState(false);
  const [form] = Form.useForm();

  const fetchBusinesses = async () => {
    try {
      setLoading(true);
      const res = await getBusinesses();
      setBusinesses(res.data.businesses || []);
    } catch (err) {
      message.error('获取业务列表失败');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBusinesses();
  }, []);

  const handleCreate = async (values) => {
    try {
      await createBusiness(values);
      message.success('创建成功');
      setModalVisible(false);
      form.resetFields();
      fetchBusinesses();
    } catch (err) {
      message.error(err.response?.data?.detail || '创建失败');
    }
  };

  const handleDelete = async (businessId) => {
    try {
      await deleteBusiness(businessId);
      message.success('删除成功');
      fetchBusinesses();
    } catch (err) {
      message.error(err.response?.data?.detail || '删除失败');
    }
  };

  const columns = [
    {
      title: 'Business ID',
      dataIndex: 'business_id',
      key: 'business_id',
      render: (text) => (
        <span>
          <TeamOutlined style={{ marginRight: 8 }} />
          {text}
        </span>
      ),
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '绑定书籍',
      dataIndex: 'book_count',
      key: 'book_count',
      width: 100,
      render: (count) => <Tag color="blue">{count || 0} 本</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status) => (
        <Tag color={status === 'active' ? 'green' : 'default'}>
          {status === 'active' ? '活跃' : '禁用'}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text) => text ? new Date(text).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => navigate(`/businesses/${record.business_id}`)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除此业务？"
            description="删除后将解除所有书籍绑定。"
            onConfirm={() => handleDelete(record.business_id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setModalVisible(true)}
        >
          创建业务
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={businesses}
        rowKey="business_id"
        loading={loading}
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title="创建业务"
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            name="business_id"
            label="Business ID"
            rules={[
              { required: true, message: '请输入 Business ID' },
              { pattern: /^[a-zA-Z0-9_-]+$/, message: '只能包含字母、数字、下划线和连字符' },
            ]}
          >
            <Input placeholder="例如: company_001" />
          </Form.Item>
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="业务名称" />
          </Form.Item>
          <Form.Item
            name="description"
            label="描述"
          >
            <TextArea rows={3} placeholder="业务描述（可选）" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Businesses;
