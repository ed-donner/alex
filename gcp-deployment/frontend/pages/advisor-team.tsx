import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { useAuth } from '@clerk/nextjs';
import Layout from '../components/Layout';
import { API_URL } from '../lib/config';
import { emitAnalysisCompleted, emitAnalysisFailed, emitAnalysisStarted } from '../lib/events';
import Head from 'next/head';

interface Agent {
  icon: string;
  name: string;
  role: string;
  description: string;
  color: string;
  bgColor: string;
}

interface Job {
  id: string;
  created_at: string;
  status: string;
  job_type: string;
}

interface AnalysisProgress {
  stage: 'idle' | 'starting' | 'planner' | 'parallel' | 'completing' | 'complete' | 'error';
  message: string;
  activeAgents: string[];
  error?: string;
}

const agents: Agent[] = [
  {
    icon: '🎯',
    name: 'Financial Planner',
    role: 'Orchestrator',
    description: 'Coordinates your financial analysis',
    color: 'text-ai-accent',
    bgColor: 'bg-ai-accent'
  },
  {
    icon: '📊',
    name: 'Portfolio Analyst',
    role: 'Reporter',
    description: 'Analyzes your holdings and performance',
    color: 'text-primary',
    bgColor: 'bg-primary'
  },
  {
    icon: '📈',
    name: 'Chart Specialist',
    role: 'Charter',
    description: 'Visualizes your portfolio composition',
    color: 'text-green-600',
    bgColor: 'bg-green-600'
  },
  {
    icon: '🎯',
    name: 'Retirement Planner',
    role: 'Retirement',
    description: 'Projects your retirement readiness',
    color: 'text-accent',
    bgColor: 'bg-accent'
  }
];

export default function AdvisorTeam() {
  const router = useRouter();
  const { getToken } = useAuth();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<AnalysisProgress>({
    stage: 'idle',
    message: '',
    activeAgents: []
  });
  const [pollInterval, setPollInterval] = useState<NodeJS.Timeout | null>(null);

  useEffect(() => {
    fetchJobs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const checkJobStatusLocal = async (jobId: string) => {
      try {
        const token = await getToken();
        const response = await fetch(`${API_URL}/api/jobs/${jobId}`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (response.ok) {
          const job = await response.json();

          if (job.status === 'completed') {
            setProgress({
              stage: 'complete',
              message: 'Analysis complete!',
              activeAgents: []
            });

            if (pollInterval) {
              clearInterval(pollInterval);
              setPollInterval(null);
            }

            // Emit completion event so other components can refresh
            emitAnalysisCompleted(jobId);

            // Also refresh our own jobs list
            fetchJobs();

            setTimeout(() => {
              router.push(`/analysis?job_id=${jobId}`);
            }, 1500);
          } else if (job.status === 'failed') {
            setProgress({
              stage: 'error',
              message: 'Analysis failed',
              activeAgents: [],
              error: job.error || 'Analysis encountered an error'
            });

            if (pollInterval) {
              clearInterval(pollInterval);
              setPollInterval(null);
            }

            // Emit failure event
            emitAnalysisFailed(jobId, job.error);

            setIsAnalyzing(false);
            setCurrentJobId(null);
          }
        }
      } catch (error) {
        console.error('Error checking job status:', error);
      }
    };

    if (currentJobId && !pollInterval) {
      const interval = setInterval(() => {
        checkJobStatusLocal(currentJobId);
      }, 2000);
      setPollInterval(interval);
    }

    return () => {
      if (pollInterval) {
        clearInterval(pollInterval);
        setPollInterval(null);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentJobId, pollInterval, router]);

  const fetchJobs = async () => {
    try {
      const token = await getToken();
      const response = await fetch(`${API_URL}/api/jobs`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setJobs(data.jobs || []);
      }
    } catch (error) {
      console.error('Error fetching jobs:', error);
    }
  };

  const startAnalysis = async () => {
    setIsAnalyzing(true);
    setProgress({
      stage: 'starting',
      message: 'Initializing analysis...',
      activeAgents: []
    });

    try {
      const token = await getToken();
      const response = await fetch(`${API_URL}/api/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          analysis_type: 'portfolio',
          options: {}
        })
      });

      if (response.ok) {
        const data = await response.json();
        setCurrentJobId(data.job_id);

        // Emit start event
        emitAnalysisStarted(data.job_id);

        setProgress({
          stage: 'planner',
          message: 'Financial Planner coordinating analysis...',
          activeAgents: ['Financial Planner']
        });

        setTimeout(() => {
          setProgress({
            stage: 'parallel',
            message: 'Agents working in parallel...',
            activeAgents: ['Portfolio Analyst', 'Chart Specialist', 'Retirement Planner']
          });
        }, 5000);
      } else {
        throw new Error('Failed to start analysis');
      }
    } catch (error) {
      console.error('Error starting analysis:', error);
      setProgress({
        stage: 'error',
        message: 'Failed to start analysis',
        activeAgents: [],
        error: error instanceof Error ? error.message : 'Unknown error'
      });
      setIsAnalyzing(false);
      setCurrentJobId(null);
    }
  };


  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-600';
      case 'failed':
        return 'text-red-500';
      case 'running':
        return 'text-blue-600';
      default:
        return 'text-gray-500';
    }
  };

  const isAgentActive = (agentName: string) => {
    return progress.activeAgents.includes(agentName);
  };

  return (
    <>
      <Head>
        <title>Advisor Team - Alex AI Financial Advisor</title>
      </Head>
      <Layout>
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-white rounded-lg shadow px-8 py-6 mb-8">
            <h1 className="text-3xl font-bold text-dark mb-2">Your AI Advisory Team</h1>
            <p className="text-gray-600">
              Meet your team of specialized AI agents that work together to provide comprehensive financial analysis.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {agents.map((agent) => (
              <div
                key={agent.name}
                className={`bg-white rounded-lg shadow-lg p-6 relative overflow-hidden transition-all duration-300 ${
                  isAgentActive(agent.name) ? 'ring-4 ring-ai-accent ring-opacity-50' : ''
                }`}
              >
                {isAgentActive(agent.name) && (
                  <div className="absolute inset-0 bg-gradient-to-br from-ai-accent/20 to-transparent animate-strong-pulse" />
                )}
                <div className="relative">
                  <div className={`text-5xl mb-4 ${isAgentActive(agent.name) ? 'animate-strong-pulse' : ''}`}>{agent.icon}</div>
                  <h3 className={`text-xl font-semibold mb-1 ${agent.color}`}>
                    {agent.name}
                  </h3>
                  <p className="text-sm text-gray-500 mb-3">{agent.role}</p>
                  <p className="text-gray-600 text-sm">{agent.description}</p>
                  {isAgentActive(agent.name) && (
                    <div className={`mt-4 inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold text-white ${agent.bgColor} animate-strong-pulse`}>
                      <span className="mr-2">●</span>
                      Active
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="bg-white rounded-lg shadow px-8 py-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-semibold text-dark">Analysis Center</h2>
              <button
                onClick={startAnalysis}
                disabled={isAnalyzing}
                className={`px-8 py-4 rounded-lg font-semibold text-white transition-all ${
                  isAnalyzing
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-ai-accent hover:bg-purple-700 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5'
                }`}
              >
                {isAnalyzing ? 'Analysis in Progress...' : 'Start New Analysis'}
              </button>
            </div>

            {isAnalyzing && (
              <div className="mb-8 p-6 bg-gradient-to-r from-ai-accent/10 to-primary/10 rounded-lg border border-ai-accent/20">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-dark">Analysis Progress</h3>
                  {progress.stage !== 'error' && progress.stage !== 'complete' && (
                    <div className="flex space-x-2">
                      <div className="w-3 h-3 bg-ai-accent rounded-full animate-strong-pulse" />
                      <div className="w-3 h-3 bg-ai-accent rounded-full animate-strong-pulse" style={{ animationDelay: '0.5s' }} />
                      <div className="w-3 h-3 bg-ai-accent rounded-full animate-strong-pulse" style={{ animationDelay: '1s' }} />
                    </div>
                  )}
                </div>

                <p className={`text-sm mb-4 ${
                  progress.stage === 'error' ? 'text-red-600' : 'text-gray-600'
                }`}>
                  {progress.message}
                </p>

                {progress.stage === 'error' && progress.error && (
                  <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                    <p className="text-sm text-red-800">{progress.error}</p>
                    <button
                      onClick={() => {
                        setIsAnalyzing(false);
                        setCurrentJobId(null);
                        setProgress({ stage: 'idle', message: '', activeAgents: [] });
                      }}
                      className="mt-3 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm font-semibold"
                    >
                      Try Again
                    </button>
                  </div>
                )}

                {progress.stage !== 'idle' && progress.stage !== 'error' && (
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-ai-accent h-2 rounded-full transition-all duration-1000"
                      style={{
                        width: progress.stage === 'starting' ? '10%' :
                               progress.stage === 'planner' ? '30%' :
                               progress.stage === 'parallel' ? '70%' :
                               progress.stage === 'completing' ? '90%' :
                               '100%'
                      }}
                    />
                  </div>
                )}
              </div>
            )}

            <div>
              <h3 className="text-lg font-semibold text-dark mb-4">Previous Analyses</h3>
              {jobs.length === 0 ? (
                <p className="text-gray-500 italic">No previous analyses found. Start your first analysis above!</p>
              ) : (
                <div className="space-y-3">
                  {jobs.slice(0, 5).map((job) => (
                    <div
                      key={job.id}
                      className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                    >
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-900">
                          Analysis #{job.id.slice(0, 8)}
                        </p>
                        <p className="text-xs text-gray-500">
                          {formatDate(job.created_at)}
                        </p>
                      </div>
                      <div className="flex items-center space-x-4">
                        <span className={`text-sm font-medium ${getStatusColor(job.status)}`}>
                          {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
                        </span>
                        {job.status === 'completed' && (
                          <button
                            onClick={() => router.push(`/analysis?job_id=${job.id}`)}
                            className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 text-sm font-semibold"
                          >
                            View
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      </Layout>
    </>
  );
}